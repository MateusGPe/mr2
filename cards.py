import csv
import qrcode
import io
import base64
import os

# --- 1. SETUP ---
csv_filename = 'students.csv'
if not os.path.exists(csv_filename):
    with open(csv_filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['register', 'name', 'class'])
        for i in range(1, 13): 
            writer.writerow([f'ID-{i:04d}', f'USER NAME {i}', f'ALPHA-{i}'])

# --- 2. QR GENERATION (Optimized for Modern High-Contrast) ---
def generate_qr_base64(data):
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=20, border=0)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode('utf-8')}"

# --- 3. MODERN FULL-PAGE TEMPLATE ---
html_start = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
    /* 1. REMOVE ALL MARGIN LIMITATIONS */
    @page { 
        size: A4; 
        margin: 0; 
    }
    body { 
        margin: 0; padding: 0; background: #fff; 
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
        -webkit-print-color-adjust: exact;
    }
    
    /* 2. PAGE AS PART OF THE CARD GRID (Full Bleed) */
    .page {
        width: 210mm;
        height: 297mm;
        display: grid;
        grid-template-columns: repeat(3, 1fr); /* 3 Columns */
        grid-template-rows: repeat(4, 1fr);    /* 4 Rows */
        page-break-after: always;
        border: 0.5pt solid black; /* Outer page border */
    }

    /* 3. SHARED BORDERS (Single Cut-Line) */
    .cell {
        border: 0.5pt solid black;
        margin: -0.25pt; 
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: space-between;
        box-sizing: border-box;
        position: relative;
        padding: 10%; /* Modern Breathing Room */
    }

    /* 4. MODERN RATIO (Optimized Space) */
    .qr-wrapper {
        width: 100%;
        flex-grow: 1;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .qr-img {
        width: 80%; /* Large focus on QR */
        height: auto;
    }

    /* Typography & Metadata */
    .content-footer {
        width: 100%;
        text-align: left;
        border-top: 2pt solid black;
        padding-top: 8px;
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
    }

    .text-block {
        display: flex;
        flex-direction: column;
    }

    .reg { 
        font-size: 14pt; 
        font-weight: 900; 
        letter-spacing: -0.5px;
        line-height: 1;
    }
    
    .name { 
        font-size: 7pt; 
        text-transform: uppercase;
        font-weight: 500;
        margin-top: 4px;
        color: #333;
    }

    /* "Page part of card" indicator */
    .page-indicator {
        font-size: 6pt;
        font-weight: bold;
        transform: rotate(-90deg);
        transform-origin: bottom right;
        white-space: nowrap;
        position: absolute;
        right: 5px;
        top: 10px;
    }

    @media print {
        .cell { border-color: black !important; }
    }
</style>
</head>
<body>
"""

html_end = "</body></html>"

def main():
    cards_html = ""
    try:
        with open(csv_filename, mode='r', encoding='utf-8') as f:
            reader = list(csv.DictReader(f))
            chunk_size = 12 
            page_num = 1
            for i in range(0, len(reader), chunk_size):
                cards_html += '<div class="page">'
                batch = reader[i : i + chunk_size]
                for row in batch:
                    qr = generate_qr_base64(row['register'])
                    cards_html += f'''
                    <div class="cell">
                        <div class="page-indicator">P.{page_num}</div>
                        <div class="qr-wrapper">
                            <img src="{qr}" class="qr-img">
                        </div>
                        <div class="content-footer">
                            <div class="text-block">
                                <span class="reg">{row['register']}</span>
                                <span class="name">{row['name']}</span>
                            </div>
                        </div>
                    </div>'''
                # Fill empty cells to keep the grid uniform
                for _ in range(chunk_size - len(batch)):
                    cards_html += '<div class="cell"></div>'
                cards_html += '</div>'
                page_num += 1

        with open("printable_cards.html", "w", encoding="utf-8") as out:
            out.write(html_start + cards_html + html_end)
        print("Success! Modern edge-to-edge layout generated.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()