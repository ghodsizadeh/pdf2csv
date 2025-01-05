from pdf2csv import convert
import pytest

@pytest.fixture
def ltr_pdf():
    return "tests/assets/ltr_test.pdf"


def test_ltr_convert(ltr_pdf):
    pdf_path = ltr_pdf
    dfs = convert(pdf_path, ltr=False)
    assert len(dfs) == 1
    df = dfs[0]
    breakpoint()
    df.columns[0] == 'بلندمدت  ميانگين.اختالف نسبت به  درصد'
    assert len(df.columns) == 6
    assert len(df) == 10
    assert df.iloc[0, 0] == 3.16


