import os
import glob
import pandas as pd

def process():
    candidates = [
        "raw-payload/dividend_payload.html",
        "dividend_payload.html"
    ]
    payload_file = None
    for c in candidates:
        if os.path.isfile(c):
            payload_file = c
            break

    if not payload_file:
        html_files = glob.glob("**/*payload*.html", recursive=True)
        if html_files:
            payload_file = html_files[0]

    if not payload_file or not os.path.exists(payload_file):
        raise FileNotFoundError(f"Missing payload file! Checked {candidates}. Current dir contents: {os.listdir('.')}")

    with open(payload_file, "r", encoding="utf-8") as f:
        raw_html = f.read()

    print(f"Loaded payload ({len(raw_html)} characters).")

    # 1. Parse tables using pandas (in-memory StringIO required for pandas 2.0+)
    import io
    dfs = pd.read_html(io.StringIO(raw_html))
    if not dfs:
        raise ValueError("No HTML tables found in payload!")

    df = dfs[0]
    print("=" * 60)
    print("Table successfully parsed on GitHub Runner!")
    print(f"Shape: {df.shape[0]} rows, {df.shape[1]} columns")
    print("=" * 60)
    print(df.head(5))

    # 2. Perform File I/O: Write to DividendDetail/*.xls and *.csv
    output_dir = "DividendDetail"
    os.makedirs(output_dir, exist_ok=True)
    xls_path = os.path.join(output_dir, "DividendDetail_2330_台積電.xls")
    csv_path = os.path.join(output_dir, "DividendDetail_2330_台積電.csv")

    with open(xls_path, "w", encoding="utf-8-sig") as f:
        f.write(raw_html)
    print(f"Successfully saved XLS file to GitHub Runner: {xls_path} ({os.path.getsize(xls_path)} bytes)")

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"Successfully saved CSV file to GitHub Runner: {csv_path} ({os.path.getsize(csv_path)} bytes)")

    # 3. Validation check
    assert df.shape[0] >= 10, f"Expected at least 10 rows, got {df.shape[0]}"
    print("Verification PASSED!")

if __name__ == "__main__":
    process()
