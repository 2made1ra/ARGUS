from app.features.catalog.csv_parser import parse_price_csv


def test_parse_price_csv_preserves_multiline_source_text() -> None:
    rows = parse_price_csv(
        "\n".join(
            [
                "id,name,category,unit,unit_price,source_text,embedding",
                '1,Свет,Аренда,шт,1200,"Первая строка',
                'вторая строка","[0.1, 0.2, 0.3]"',
            ],
        ),
    )

    assert len(rows) == 1
    assert rows[0].row_number == 2
    assert rows[0].raw["source_text"] == "Первая строка\nвторая строка"
    assert rows[0].raw["embedding"] == "[0.1, 0.2, 0.3]"
    assert rows[0].legacy_embedding_present is True
    assert rows[0].legacy_embedding_dim == 3


def test_parse_price_csv_preserves_empty_category_and_source_text() -> None:
    rows = parse_price_csv(
        "\n".join(
            [
                "id,name,category,unit,unit_price,source_text,embedding",
                "2,Монтаж,,усл.,3500,,",
            ],
        ),
    )

    assert rows[0].raw["category"] == ""
    assert rows[0].raw["source_text"] == ""
    assert rows[0].legacy_embedding_present is False
    assert rows[0].legacy_embedding_dim is None


def test_parse_price_csv_accepts_bytes_input() -> None:
    rows = parse_price_csv(
        "id,name,category,unit,unit_price,source_text,embedding\n"
        "3,Пульт,Оборудование,шт,2000,Ручной ввод,\"[1, 2]\"\n".encode(),
    )

    assert rows[0].raw["name"] == "Пульт"
    assert rows[0].legacy_embedding_present is True
    assert rows[0].legacy_embedding_dim == 2
