import os
import uuid
import datetime
from flask import Flask, request, jsonify, render_template_string, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# In-memory print queues
PRINT_JOBS = []
FILES_STORAGE = {}

# Dukano ka Configuration: Yahan naye dukandar ka name, rates aur unka UPI ID daalein
SHOPS = {
    "default": {
        "name": "QuickPrint Catalyst",
        "upi_id": "yourname@okhdfcbank",
        "bw_rate": 2.0,
        "color_rate": 10.0
    },
    "gupta_stationery": {
        "name": "Gupta Stationery & Xerox",
        "upi_id": "guptaji@upi",  # Dukandar ka asli UPI ID
        "bw_rate": 2.0,
        "color_rate": 10.0
    },
    "sharma_cyber": {
        "name": "Sharma Cyber Cafe",
        "upi_id": "sharmacyber@ybl",  # Dukandar ka asli UPI ID
        "bw_rate": 3.0,
        "color_rate": 8.0
    }
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Document Printing</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f0f2f5; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }
        .card { background: white; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.08); width: 100%; max-width: 420px; padding: 24px; box-sizing: border-box; text-align: center; }
        h2 { margin: 0 0 4px 0; color: #111; }
        p.subtitle { color: #666; font-size: 13px; margin-top: 0; margin-bottom: 20px; }
        .upload-box { border: 2px dashed #2563eb; border-radius: 12px; padding: 24px; cursor: pointer; background: #eff6ff; margin-bottom: 20px; }
        .form-row { display: flex; gap: 12px; margin-bottom: 16px; }
        .form-group { flex: 1; text-align: left; }
        label { font-size: 13px; color: #333; font-weight: 500; display: block; margin-bottom: 6px; }
        select, input { width: 100%; padding: 10px; border-radius: 8px; border: 1px solid #ccc; font-size: 14px; box-sizing: border-box; }
        .bill-box { background: #fafafa; border-radius: 8px; padding: 12px; margin-bottom: 20px; font-size: 13px; text-align: left; }
        .bill-row { display: flex; justify-content: space-between; margin-bottom: 6px; }
        .total-row { display: flex; justify-content: space-between; font-weight: bold; font-size: 15px; border-top: 1px solid #ddd; padding-top: 6px; }
        .btn { background: #2563eb; color: white; border: none; border-radius: 8px; width: 100%; padding: 14px; font-size: 16px; font-weight: bold; cursor: pointer; }
        .btn:disabled { background: #93c5fd; }
        #status-card { display: none; }
        .spinner { border: 4px solid #f3f3f3; border-top: 4px solid #2563eb; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 20px auto; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .creator-badge { margin-top: 22px; padding-top: 12px; border-top: 1px dashed #cbd5e1; font-size: 12px; color: #64748b; line-height: 1.4; }
    </style>
</head>
<body>
    <div class="card" id="upload-card">
        <h2 id="shop-name">QuickPrint Spot</h2>
        <p class="subtitle">Direct UPI Pay & Instant Print</p>

        <div class="upload-box" onclick="document.getElementById('file-input').click()">
            <span id="file-label">Tap to Select Document<br><small style="color: #666;">PDF, Images, TXT</small></span>
            <input type="file" id="file-input" style="display: none;" onchange="handleFile(this)">
        </div>

        <div class="form-row">
            <div class="form-group">
                <label>Color Mode</label>
                <select id="color-mode" onchange="calculateTotal()">
                    <option value="bw">B & W</option>
                    <option value="color">Color</option>
                </select>
            </div>
            <div class="form-group">
                <label>Copies</label>
                <input type="number" id="copies" value="1" min="1" onchange="calculateTotal()">
            </div>
        </div>

        <div class="bill-box">
            <div class="bill-row"><span>Copies:</span><span id="bill-copies">1</span></div>
            <div class="bill-row"><span>Rate per Page:</span><span id="bill-rate">₹2.00</span></div>
            <div class="total-row"><span>Grand Total:</span><span id="bill-total" style="color: #2563eb;">₹2.00</span></div>
        </div>

        <button class="btn" id="pay-btn" onclick="startPayAndPrint()">Pay via UPI & Print</button>

        <div class="creator-badge">
            Engineered & Built by <b style="color: #0f172a;">Akash Verma</b><br>
            <span style="font-size: 10px; color: #94a3b8; letter-spacing: 0.5px;">AUTONOMOUS PRINT CLOUD ENGINE</span>
        </div>
    </div>

    <div class="card" id="status-card">
        <div class="spinner"></div>
        <h2>Sending to Printer...</h2>
        <p style="color: #64748b; font-size: 14px;">Aapka document print queue me bhej diya gaya hai. Dukandar ke printer se print nikal raha hai.</p>
        <button class="btn" onclick="location.reload()" style="background: #111; margin-top: 15px;">Print Another File</button>

        <div class="creator-badge">
            Engineered & Built by <b style="color: #0f172a;">Akash Verma</b>
        </div>
    </div>

    <script>
        const urlParams = new URLSearchParams(window.location.search);
        const shopId = urlParams.get('shop') || 'default';
        let shopData = { name: "QuickPrint Spot", upi_id: "test@upi", bw_rate: 2.0, color_rate: 10.0 };
        let selectedFile = null;

        fetch(`/api/shop-info?shop=${shopId}`)
            .then(res => res.json())
            .then(data => {
                shopData = data;
                document.getElementById('shop-name').innerText = data.name;
                document.querySelector('#color-mode option[value="bw"]').innerText = `B & W (₹${data.bw_rate}/page)`;
                document.querySelector('#color-mode option[value="color"]').innerText = `Color (₹${data.color_rate}/page)`;
                calculateTotal();
            });

        function handleFile(input) {
            if (input.files && input.files[0]) {
                selectedFile = input.files[0];
                document.getElementById('file-label').innerText = selectedFile.name;
            }
        }

        function calculateTotal() {
            const mode = document.getElementById('color-mode').value;
            const copies = parseInt(document.getElementById('copies').value) || 1;
            const rate = (mode === 'color') ? shopData.color_rate : shopData.bw_rate;
            const total = rate * copies;
            document.getElementById('bill-copies').innerText = copies;
            document.getElementById('bill-rate').innerText = `₹${rate.toFixed(2)}`;
            document.getElementById('bill-total').innerText = `₹${total.toFixed(2)}`;
            return total;
        }

        async function startPayAndPrint() {
            if (!selectedFile) {
                alert("Please select a document first.");
                return;
            }

            const btn = document.getElementById('pay-btn');
            btn.disabled = true;
            btn.innerText = "Processing...";

            const total = calculateTotal();
            const formData = new FormData();
            formData.append("file", selectedFile);
            formData.append("shop_id", shopId);
            formData.append("color_mode", document.getElementById('color-mode').value);
            formData.append("copies", document.getElementById('copies').value);
            formData.append("amount", total);

            const res = await fetch("/api/submit-job", { method: "POST", body: formData });
            const data = await res.json();

            if (data.status === "success") {
                const upiLink = `upi://pay?pa=${shopData.upi_id}&pn=${encodeURIComponent(shopData.name)}&am=${total}&cu=INR&tn=Printout_${selectedFile.name.substring(0,10)}`;
                document.getElementById('upload-card').style.display = 'none';
                document.getElementById('status-card').style.display = 'block';
                window.location.href = upiLink;
            } else {
                alert("Error sending file to server.");
                btn.disabled = false;
                btn.innerText = "Pay via UPI & Print";
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/shop-info')
def get_shop_info():
    shop_id = request.args.get('shop', 'default')
    return jsonify(SHOPS.get(shop_id, SHOPS['default']))

@app.route('/api/submit-job', methods=['POST'])
def submit_job():
    shop_id = request.form.get('shop_id', 'default')
    color_mode = request.form.get('color_mode', 'bw')
    copies = int(request.form.get('copies', 1))
    amount = float(request.form.get('amount', 2.0))
    file = request.files.get('file')

    job_id = str(uuid.uuid4())
    file_bytes = file.read()
    FILES_STORAGE[job_id] = {
        "filename": file.filename,
        "content": file_bytes
    }

    PRINT_JOBS.append({
        "job_id": job_id,
        "shop_id": shop_id,
        "filename": file.filename,
        "color_mode": color_mode,
        "copies": copies,
        "amount": amount,
        "time": datetime.datetime.now().strftime("%I:%M %p"),
        "status": "ready_to_print"
    })

    return jsonify({"status": "success", "job_id": job_id})

@app.route('/api/get-pending-jobs')
def get_pending_jobs():
    shop_id = request.args.get('shop_id', 'default')
    jobs = [j for j in PRINT_JOBS if j['shop_id'] == shop_id and j['status'] == 'ready_to_print']
    return jsonify(jobs)

@app.route('/api/download-file/<job_id>')
def download_file(job_id):
    if job_id in FILES_STORAGE:
        file_data = FILES_STORAGE[job_id]
        return Response(file_data['content'], headers={"Content-Disposition": f"attachment; filename={file_data['filename']}"})
    return "File Not Found", 404

@app.route('/api/complete-job/<job_id>', methods=['POST'])
def complete_job(job_id):
    global PRINT_JOBS
    PRINT_JOBS = [j for j in PRINT_JOBS if j['job_id'] != job_id]
    FILES_STORAGE.pop(job_id, None)
    return jsonify({"status": "completed"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
