import os
import uuid
import datetime
from flask import Flask, request, jsonify, render_template_string, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

PRINT_JOBS = []
FILES_STORAGE = {}

# Sabhi shop IDs lowercase me rakhi gayi hain
SHOPS = {
    "default": {
        "name": "QuickPrint Catalyst",
        "upi_id": "yourname@okhdfcbank",
        "bw_rate": 2.0,
        "color_rate": 10.0
    },
    "gupta_stationery": {
        "name": "Gupta Stationery and Xerox",
        "upi_id": "verma.671@superyes",
        "bw_rate": 2.0,
        "color_rate": 10.0
    },
    "ranjan_stationery": {
        "name": "Ranjan Stationery and Xerox",
        "upi_id": "ranjan@upi",
        "bw_rate": 2.0,
        "color_rate": 10.0
    },
    "sharma_cyber": {
        "name": "Sharma Cyber Cafe",
        "upi_id": "sharmacyber@ybl",
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
    <title>{{ shop_data.name }} - Self Print</title>
    <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f0f2f5; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }
        .card { background: white; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.08); width: 100%; max-width: 420px; padding: 24px; box-sizing: border-box; text-align: center; }
        h2 { margin: 0 0 4px 0; color: #111; font-size: 22px; }
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
        <h2 id="shop-name">{{ shop_data.name }}</h2>
        <p class="subtitle">Direct Online Pay & Instant Print</p>

        <div class="upload-box" onclick="document.getElementById('file-input').click()">
            <span id="file-label">Tap to Select Document<br><small style="color: #666;">PDF, Images, TXT</small></span>
            <input type="file" id="file-input" style="display: none;" onchange="handleFile(this)">
        </div>

        <div class="form-row">
            <div class="form-group">
                <label>Color Mode</label>
                <select id="color-mode" onchange="calculateTotal()">
                    <option value="bw">B & W (₹{{ "%.2f"|format(shop_data.bw_rate) }}/page)</option>
                    <option value="color">Color (₹{{ "%.2f"|format(shop_data.color_rate) }}/page)</option>
                </select>
            </div>
            <div class="form-group">
                <label>Copies</label>
                <input type="number" id="copies" value="1" min="1" onchange="calculateTotal()">
            </div>
        </div>

        <div class="bill-box">
            <div class="bill-row"><span>Copies:</span><span id="bill-copies">1</span></div>
            <div class="bill-row"><span>Rate per Page:</span><span id="bill-rate">₹{{ "%.2f"|format(shop_data.bw_rate) }}</span></div>
            <div class="total-row"><span>Grand Total:</span><span id="bill-total" style="color: #2563eb;">₹{{ "%.2f"|format(shop_data.bw_rate) }}</span></div>
        </div>

        <button class="btn" id="pay-btn" onclick="startPayAndPrint()">Pay & Print</button>

        <div class="creator-badge">
            Engineered & Built by <b style="color: #0f172a;">Akash Verma</b><br>
            <span style="font-size: 10px; color: #94a3b8; letter-spacing: 0.5px;">AUTONOMOUS PRINT CLOUD ENGINE</span>
        </div>
        
        <div style="margin-top: 15px; font-size: 11px; color: #64748b;">
            <a href="/terms" style="color: #64748b; text-decoration: none; margin: 0 5px;">Terms</a> |
            <a href="/privacy" style="color: #64748b; text-decoration: none; margin: 0 5px;">Privacy</a> |
            <a href="/refund" style="color: #64748b; text-decoration: none; margin: 0 5px;">Refunds</a> |
            <a href="/contact" style="color: #64748b; text-decoration: none; margin: 0 5px;">Contact Us</a>
        </div>
    </div>

    <div class="card" id="status-card">
        <div class="spinner"></div>
        <h2 style="color: #0f172a; margin-bottom: 6px;">Printing Document</h2>
        <p style="color: #64748b; font-size: 13px; line-height: 1.5; margin: 0 0 16px 0;">Payment verified. Document sent to counter printer.</p>
        <button class="btn" onclick="location.reload()" style="background: #0f172a; padding: 12px; font-size: 14px;">Print Another Document</button>

        <div class="creator-badge">
            Engineered & Built by <b style="color: #0f172a;">Akash Verma</b><br>
            <span style="font-size: 10px; color: #94a3b8; letter-spacing: 0.5px;">AUTONOMOUS PRINT CLOUD ENGINE</span>
        </div>
    </div>

    <script>
        const shopId = "{{ shop_id }}";
        const shopData = {
            name: "{{ shop_data.name }}",
            upi_id: "{{ shop_data.upi_id }}",
            bw_rate: parseFloat("{{ shop_data.bw_rate }}"),
            color_rate: parseFloat("{{ shop_data.color_rate }}")
        };
        const rzpKey = "rzp_test_TS2Vq0G1hlAz2x";
        let selectedFile = null;

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

            // Step 1: Upload file & create pending job
            const res = await fetch("/api/initiate-job", { method: "POST", body: formData });
            const data = await res.json();

            if (data.status === "initiated") {
                const jobId = data.job_id;

                // Step 2: Open Razorpay Checkout modal
                const options = {
                    "key": rzpKey,
                    "amount": Math.round(total * 100), // Amount in paise
                    "currency": "INR",
                    "name": shopData.name,
                    "description": "Instant Document Printout",
                    "handler": async function (response) {
                        // Step 3: Trigger Print ONLY after success
                        const verifyRes = await fetch("/api/verify-and-print", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({
                                job_id: jobId,
                                razorpay_payment_id: response.razorpay_payment_id
                            })
                        });
                        const verifyData = await verifyRes.json();
                        if (verifyData.status === "success") {
                            document.getElementById('upload-card').style.display = 'none';
                            document.getElementById('status-card').style.display = 'block';
                        }
                    },
                    "modal": {
                        "ondismiss": function() {
                            btn.disabled = false;
                            btn.innerText = "Pay & Print";
                        }
                    },
                    "theme": { "color": "#2563eb" }
                };

                const rzp = new Razorpay(options);
                rzp.open();
            } else {
                alert("Error initializing upload.");
                btn.disabled = false;
                btn.innerText = "Pay & Print";
            }
        }
    </script>
</body>
</html>
"""

POLICY_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>{{ title }} - QuickPrint</title><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{font-family:sans-serif;max-width:700px;margin:40px auto;padding:0 20px;line-height:1.6;color:#333;}</style></head>
<body>
    <h2>{{ title }}</h2>
    <div>{{ content | safe }}</div>
    <p><a href="/">← Back to Home</a></p>
</body>
</html>
"""

@app.route('/')
def home():
    shop_param = request.args.get('shop', 'default').lower()
    shop_info = SHOPS.get(shop_param, SHOPS['default'])
    return render_template_string(HTML_TEMPLATE, shop_id=shop_param, shop_data=shop_info)

@app.route('/terms')
def terms():
    content = "<p>QuickPrint enables instant local printing. Users are responsible for uploaded document content. Service availability depends on local shop hardware status.</p>"
    return render_template_string(POLICY_TEMPLATE, title="Terms and Conditions", content=content)

@app.route('/privacy')
def privacy():
    content = "<p>We do not store your documents permanently. Files are stored temporarily in memory only to complete the print job and are purged automatically.</p>"
    return render_template_string(POLICY_TEMPLATE, title="Privacy Policy", content=content)

@app.route('/refund')
def refund():
    content = "<p>If a print job fails due to a machine paper jam or hardware offline error after successful payment, a 100% refund is initiated within 24 hours to the original payment source.</p>"
    return render_template_string(POLICY_TEMPLATE, title="Cancellation & Refund Policy", content=content)

@app.route('/contact')
def contact():
    content = "<p>For issues or support queries, contact us at:<br><b>Email:</b> support@quickprint.local<br><b>Operated by:</b> Akash Verma</p>"
    return render_template_string(POLICY_TEMPLATE, title="Contact Us", content=content)

@app.route('/api/initiate-job', methods=['POST'])
def initiate_job():
    shop_id = request.form.get('shop_id', 'default').lower()
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

    # Job is kept in pending state (will NOT print until payment verified)
    PRINT_JOBS.append({
        "job_id": job_id,
        "shop_id": shop_id,
        "filename": file.filename,
        "color_mode": color_mode,
        "copies": copies,
        "amount": amount,
        "time": datetime.datetime.now().strftime("%I:%M %p"),
        "status": "payment_pending"
    })

    return jsonify({"status": "initiated", "job_id": job_id})

@app.route('/api/verify-and-print', methods=['POST'])
def verify_and_print():
    data = request.get_json() or {}
    job_id = data.get('job_id')
    payment_id = data.get('razorpay_payment_id')

    if not payment_id or not job_id:
        return jsonify({"status": "failed", "error": "Invalid payment proof"}), 400

    # Mark job as ready for the client printer
    for job in PRINT_JOBS:
        if job['job_id'] == job_id:
            job['status'] = 'ready_to_print'
            job['payment_id'] = payment_id
            return jsonify({"status": "success"})

    return jsonify({"status": "failed", "error": "Job not found"}), 404

@app.route('/api/get-pending-jobs')
def get_pending_jobs():
    shop_id = request.args.get('shop_id', 'default').lower()
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
