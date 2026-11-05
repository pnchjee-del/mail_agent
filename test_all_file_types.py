"""
Comprehensive validation test for all supported file formats:
.txt, .docx, .xlsx, .pdf, .png, .gif, .csv, .zip, .sqlite, and generic .bin
"""

import os
import io
import tempfile
import sqlite3
import zipfile
from PIL import Image
import docx
import openpyxl
import pypdf
from file_reader import FileReader


def run_tests():
    print("=" * 60)
    print("🚀 Running Comprehensive File Reader Multi-Format Tests")
    print("=" * 60)

    reader = FileReader()
    temp_dir = tempfile.mkdtemp()
    print(f"Working in test directory: {temp_dir}\n")

    test_results = {}

    try:
        # 1. Plain Text (.txt)
        txt_path = os.path.join(temp_dir, "contract.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("Services Agreement\nClient: Globex Corp\nAmount: $25,000\nDeliverable: Web Portal\nStatus: Pending Approval")
        r_txt = reader.read_file(txt_path)
        assert r_txt["file_type"] == "Plain Text"
        assert r_txt["metadata"]["word_count"] > 5
        test_results[".txt"] = f"✅ Passed ({r_txt['file_type']}, {r_txt['metadata']['word_count']} words)"
        print(f"1. .txt:  {test_results['.txt']}")

        # 2. Word Document (.docx)
        docx_path = os.path.join(temp_dir, "meeting_notes.docx")
        doc = docx.Document()
        doc.add_heading("Board of Directors Meeting", level=1)
        doc.add_paragraph("All members voted in favor of the annual budget.")
        tbl = doc.add_table(rows=3, cols=2)
        tbl.rows[0].cells[0].text = "Department"
        tbl.rows[0].cells[1].text = "Budget"
        tbl.rows[1].cells[0].text = "Engineering"
        tbl.rows[1].cells[1].text = "$500,000"
        tbl.rows[2].cells[0].text = "Marketing"
        tbl.rows[2].cells[1].text = "$200,000"
        doc.save(docx_path)
        r_docx = reader.read_file(docx_path)
        assert r_docx["file_type"] == "Word Document"
        assert len(r_docx["tables"]) == 1
        test_results[".docx"] = f"✅ Passed ({r_docx['file_type']}, {len(r_docx['tables'])} table, {r_docx['metadata']['word_count']} words)"
        print(f"2. .docx: {test_results['.docx']}")

        # 3. Excel Spreadsheet (.xlsx)
        xlsx_path = os.path.join(temp_dir, "financial_model.xlsx")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Q4 Financials"
        ws.append(["Category", "October", "November", "December"])
        ws.append(["Sales", 12000, 14500, 21000])
        ws.append(["COGS", 4000, 4800, 6200])
        wb.save(xlsx_path)
        r_xlsx = reader.read_file(xlsx_path)
        assert r_xlsx["file_type"] == "Excel Spreadsheet"
        assert "Q4 Financials" in r_xlsx["metadata"]["sheets"]
        test_results[".xlsx"] = f"✅ Passed ({r_xlsx['file_type']}, sheets: {r_xlsx['metadata']['sheets']})"
        print(f"3. .xlsx: {test_results['.xlsx']}")

        # 4. PDF Document (.pdf)
        pdf_path = os.path.join(temp_dir, "policy.pdf")
        writer = pypdf.PdfWriter()
        page = writer.add_blank_page(width=300, height=400)
        # Note: blank page test
        with open(pdf_path, "wb") as pf:
            writer.write(pf)
        r_pdf = reader.read_file(pdf_path)
        assert r_pdf["file_type"] == "PDF Document"
        assert r_pdf["metadata"]["page_count"] == 1
        test_results[".pdf"] = f"✅ Passed ({r_pdf['file_type']}, {r_pdf['metadata']['page_count']} page)"
        print(f"4. .pdf:  {test_results['.pdf']}")

        # 5. PNG Image (.png)
        png_path = os.path.join(temp_dir, "architecture.png")
        img = Image.new("RGBA", (256, 128), color=(40, 120, 220, 255))
        img.save(png_path, format="PNG")
        r_png = reader.read_file(png_path)
        assert r_png["file_type"] == "PNG Image"
        assert r_png["metadata"]["dimensions"] == "256 x 128"
        test_results[".png"] = f"✅ Passed ({r_png['file_type']}, {r_png['metadata']['dimensions']})"
        print(f"5. .png:  {test_results['.png']}")

        # 6. Animated GIF (.gif)
        gif_path = os.path.join(temp_dir, "loading.gif")
        frame1 = Image.new("RGB", (64, 64), color="orange")
        frame2 = Image.new("RGB", (64, 64), color="purple")
        frame3 = Image.new("RGB", (64, 64), color="cyan")
        frame1.save(gif_path, format="GIF", save_all=True, append_images=[frame2, frame3], duration=150, loop=0)
        r_gif = reader.read_file(gif_path)
        assert r_gif["file_type"] == "GIF Image"
        assert r_gif["metadata"]["is_animated"] is True
        assert r_gif["metadata"]["frame_count"] == 3
        test_results[".gif"] = f"✅ Passed ({r_gif['file_type']}, animated: {r_gif['metadata']['is_animated']}, frames: {r_gif['metadata']['frame_count']})"
        print(f"6. .gif:  {test_results['.gif']}")

        # 7. Generic Binary File (.bin)
        bin_path = os.path.join(temp_dir, "firmware.bin")
        raw_binary = b"\x7fELF" + b"\x00\x01\x02\x03\xff\xfe\xfd" * 20 + b"VERSION=3.14.0_BUILD_2026\x00ROOT_DIR=/usr/bin\x00"
        with open(bin_path, "wb") as bf:
            bf.write(raw_binary)
        r_bin = reader.read_file(bin_path)
        assert r_bin["file_type"] == "Linux ELF Executable"
        assert r_bin["metadata"]["entropy"] > 0
        assert len(r_bin["metadata"]["sample_strings"]) > 0
        test_results[".bin"] = f"✅ Passed ({r_bin['file_type']}, entropy: {r_bin['metadata']['entropy']}, strings: {r_bin['metadata']['sample_strings']})"
        print(f"7. .bin:  {test_results['.bin']}")

        # 8. CSV Tabular (.csv)
        csv_path = os.path.join(temp_dir, "inventory.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("SKU,Item,Qty,Price\nA101,Monitor,15,220.00\nB204,Keyboard,45,45.50\nC309,Mouse,80,25.00")
        r_csv = reader.read_file(csv_path)
        assert r_csv["file_type"] == "CSV Spreadsheet"
        assert r_csv["metadata"]["rows"] == 4
        test_results[".csv"] = f"✅ Passed ({r_csv['file_type']}, {r_csv['metadata']['rows']} rows)"
        print(f"8. .csv:  {test_results['.csv']}")

        # 9. ZIP Archive (.zip)
        zip_path = os.path.join(temp_dir, "bundle.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("readme.txt", "Bundle instructions and setup guide.")
            zf.writestr("config.json", '{"version": "1.0", "active": true}')
        r_zip = reader.read_file(zip_path)
        assert r_zip["file_type"] == "ZIP Archive"
        assert r_zip["metadata"]["file_count"] == 2
        test_results[".zip"] = f"✅ Passed ({r_zip['file_type']}, {r_zip['metadata']['file_count']} files)"
        print(f"9. .zip:  {test_results['.zip']}")

        # 10. SQLite Database (.sqlite)
        db_path = os.path.join(temp_dir, "local.sqlite")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT);")
        cur.execute("INSERT INTO users VALUES (1, 'Alice', 'alice@company.com');")
        cur.execute("INSERT INTO users VALUES (2, 'Bob', 'bob@company.com');")
        conn.commit()
        conn.close()
        r_db = reader.read_file(db_path)
        assert r_db["file_type"] == "SQLite Database"
        assert "users" in r_db["metadata"]["tables"]
        test_results[".sqlite"] = f"✅ Passed ({r_db['file_type']}, tables: {r_db['metadata']['tables']})"
        print(f"10. .sqlite: {test_results['.sqlite']}")

        print("\n" + "=" * 60)
        print("🎉 ALL 10 FILE FORMAT TESTS PASSED SUCCESSFULLY!")
        print("=" * 60)

    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    run_tests()
