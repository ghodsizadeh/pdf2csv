from pdf2csv import convert
import pytest

@pytest.fixture
def rtl_pdf():
    return "tests/assets/rtl_test.pdf"


def test_rtl_convert(rtl_pdf):
    pdf_path = rtl_pdf
    dfs = convert(pdf_path, rtl=True)
    assert len(dfs) == 1
    df = dfs[0]
    df.columns[0] == 'بلندمدت  ميانگين.اختالف نسبت به  درصد'
    assert len(df.columns) == 6
    assert len(df) == 10
    assert df.iloc[0, 0] == -44


