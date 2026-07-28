"""Tests for normalized self-referencing category records."""

from lunchmoney.models import CategoryObject, ChildCategoryObject
from sqlalchemy import DateTime, String, inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable
from sqlalchemy.types import TypeDecorator
from sqlmodel import SQLModel, Session, create_engine

from lunchmoney_mcp.database.models import Category, CategoryKind
from factories import category_object, child_category_object


def test_parent_category_round_trips_children_shape_independently_of_group() -> None:
    """Preserve generated-valid null and empty children shapes for every group state."""
    for is_group, children in (
        (False, None),
        (False, []),
        (True, None),
        (True, []),
    ):
        api_parent = category_object(children=children).model_copy(
            update={"is_group": is_group}
        )

        converted = Category.from_api(api_parent).to_api()

        assert isinstance(converted, CategoryObject)
        assert converted.model_dump(mode="json") == api_parent.model_dump(mode="json")


def test_category_graph_round_trip_is_exact_and_preserves_child_order() -> None:
    """Build an owned category graph and preserve its complete API JSON."""
    first_child = child_category_object()
    second_child = first_child.model_copy(
        update={"id": 12, "name": "Synthetic Second Child", "order": 3}
    )
    api_parent = category_object(children=[first_child, second_child])

    record = Category.from_api(api_parent)

    assert record.kind == CategoryKind.PARENT
    assert [child.id for child in record.children] == [11, 12]
    assert [child.kind for child in record.children] == [
        CategoryKind.CHILD,
        CategoryKind.CHILD,
    ]
    assert all(child.group_id == record.id for child in record.children)
    assert all(child.parent is record for child in record.children)
    assert record.to_api().model_dump(mode="json") == api_parent.model_dump(mode="json")


def test_child_category_conversion_is_exact_and_deterministic() -> None:
    """Convert child rows to the generated child category schema by kind."""
    api_child = child_category_object()
    child = Category.from_api(category_object(children=[api_child])).children[0]

    converted = child.to_child_api()

    assert isinstance(converted, ChildCategoryObject)
    assert converted.model_dump(mode="json") == api_child.model_dump(mode="json")
    assert isinstance(child.to_api(), ChildCategoryObject)


def test_parent_category_conversion_uses_parent_schema_without_children() -> None:
    """Retain a parent discriminator when an API category has no children."""
    api_parent = category_object()

    converted = Category.from_api(api_parent).to_api()

    assert isinstance(converted, CategoryObject)
    assert converted.model_dump(mode="json") == api_parent.model_dump(mode="json")


def test_empty_category_group_preserves_empty_children_array() -> None:
    """Distinguish an empty category group from a non-group category."""
    api_parent = category_object(children=[])

    converted = Category.from_api(api_parent).to_api()

    assert isinstance(converted, CategoryObject)
    assert converted.model_dump(mode="json") == api_parent.model_dump(mode="json")


def test_category_table_covers_generated_scalar_union() -> None:
    """Map every generated scalar category field plus the discriminator."""
    api_fields = set(CategoryObject.model_fields) | set(
        ChildCategoryObject.model_fields
    )
    api_scalar_fields = api_fields - {"children"}
    table = SQLModel.metadata.tables["categories"]

    assert set(table.c.keys()) == api_scalar_fields | {
        "archived_at_offset_minutes",
        "children_present",
        "created_at_offset_minutes",
        "kind",
        "updated_at_offset_minutes",
    }
    assert isinstance(table.c.kind.type, String)
    assert table.c.collapsed.nullable is True
    assert table.c.children_present.nullable is False
    assert next(iter(table.c.group_id.foreign_keys)).ondelete == "CASCADE"


def test_category_timestamp_columns_are_native_and_retain_source_offsets() -> None:
    """Use portable native datetimes plus nullable source-offset state."""
    table = SQLModel.metadata.tables["categories"]
    for field_name in ("updated_at", "created_at", "archived_at"):
        column_type = table.c[field_name].type
        assert isinstance(column_type, TypeDecorator)
        assert isinstance(column_type.impl, DateTime)
        assert column_type.impl.timezone is True
        assert table.c[f"{field_name}_offset_minutes"].nullable is True


def test_category_table_compiles_for_postgresql() -> None:
    """Compile source-shape timestamp storage to PostgreSQL native columns."""
    table = SQLModel.metadata.tables["categories"]

    ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))

    assert "CREATE TABLE categories" in ddl
    assert "TIMESTAMP WITH TIME ZONE" in ddl


def test_category_group_id_is_a_self_foreign_key() -> None:
    """Link child categories to parent rows through the category table."""
    table = SQLModel.metadata.tables["categories"]

    assert {
        foreign_key.target_fullname for foreign_key in table.c.group_id.foreign_keys
    } == {"categories.id"}


def test_category_relationships_own_children() -> None:
    """Configure explicit bidirectional self relationships and orphan deletion."""
    mapper = inspect(Category)
    parent_relationship = mapper.relationships["parent"]
    children_relationship = mapper.relationships["children"]
    table = SQLModel.metadata.tables["categories"]

    assert parent_relationship.back_populates == "children"
    assert parent_relationship.remote_side == {table.c.id}
    assert children_relationship.back_populates == "parent"
    assert children_relationship.single_parent is True
    assert children_relationship.cascade.delete is True
    assert children_relationship.cascade.delete_orphan is True


def test_category_relationship_persists_order_and_deletes_orphans() -> None:
    """Reload children in API order and delete rows removed from the owned graph."""
    first_child = child_category_object()
    second_child = first_child.model_copy(
        update={"id": 12, "name": "Synthetic Second Child", "order": 3}
    )
    record = Category.from_api(category_object(children=[first_child, second_child]))
    engine = create_engine("sqlite://")
    SQLModel.metadata.tables["categories"].create(engine)

    with Session(engine) as session:
        session.add(record)
        session.commit()
        session.expire_all()

        reloaded = session.get(Category, record.id)

        assert reloaded is not None
        assert [child.id for child in reloaded.children] == [11, 12]

        orphan = reloaded.children.pop(0)
        session.commit()

        assert session.get(Category, orphan.id) is None


def test_category_relationship_orders_null_positions_by_name() -> None:
    """Load null-ordered children first and alphabetically as the API specifies."""
    child = child_category_object()
    zulu_child = child.model_copy(
        update={"id": 11, "name": "Zulu Child", "order": None}
    )
    alpha_child = child.model_copy(
        update={"id": 12, "name": "Alpha Child", "order": None}
    )
    ordered_child = child.model_copy(
        update={"id": 13, "name": "Ordered Child", "order": 1}
    )
    record = Category.from_api(
        category_object(children=[zulu_child, alpha_child, ordered_child])
    )
    engine = create_engine("sqlite://")
    SQLModel.metadata.tables["categories"].create(engine)

    with Session(engine) as session:
        session.add(record)
        session.commit()
        session.expire_all()

        reloaded = session.get(Category, record.id)

        assert reloaded is not None
        assert [child.id for child in reloaded.children] == [12, 11, 13]
