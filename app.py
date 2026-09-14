import os
import uuid
import datetime
import razorpay
from flask import Flask, request, jsonify, render_template_string, Response

app = Flask(__name__)

# Razorpay Credentials
RAZORPAY_KEY_ID = "rzp_test_TS2Vq0G1hlAz2x"
RAZORPAY_KEY_SECRET = "1Ur7xBBw5LyO1d2H3RqSWVho"

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

PRINT_JOBS = []
FILES_STORAGE = {}

SHOPS = {
    "default": {
        "name": "Dristi Online Center",
        "upi_id": "Q159163070@ybl",
        "bw_rate": 2.0,
        "color_rate": 10.0
    },
    "ranjan_stationery": {
        "name": "Dristi Online Center",
        "upi_id": "Q159163070@ybl",
        "bw_rate": 2.0,
        "color_rate": 10.0
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
        <p class="subtitle">Online Self Print Kiosk</p>

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

        <button class="btn" id="pay-btn" onclick="startPayFlow()">Pay & Instant Print</button>

        <div class="creator-badge">
            Engineered & Built by <b style="color: #0f172a;">Akash Verma</b><br>
            <span style="font-size: 10px; color: #94a3b8; letter-spacing: 0.5px;">AUTONOMOUS PRINT CLOUD ENGINE</span>
        </div>
    </div>

    <div class="card" id="status-card">
        <div class="spinner" id="status-spinner"></div>
        <h2 id="status-title" style="color: #0f172a; margin-bottom: 6px;">Processing Payment</h2>
        <p id="status-desc" style="color: #64748b; font-size: 13px; line-height: 1.5; margin: 0 0 16px 0;">Awaiting confirmation from bank...</p>
        <button class="btn" onclick="location.reload()" style="background: #0f172a; padding: 12px; font-size: 14px;">Print Another Document</button>
    </div>

    <script>
        const shopId = "{{ shop_id }}";
        const shopData = {
            name: "{{ shop_data.name }}",
            upi_id: "{{ shop_data.upi_id }}",
            bw_rate: parseFloat("{{ shop_data.bw_rate }}"),
            color_rate: parseFloat("{{ shop_data.color_rate }}")
        };
        const rzpKey = "{{ razorpay_key_id }}";
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

        async function startPayFlow() {
            if (!selectedFile) {
                alert("Please select a document first.");
                return;
            }

            const btn = document.getElementById('pay-btn');
            btn.disabled = true;
            btn.innerText = "Initiating Order...";

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
                const options = {
                    "key": rzpKey,
                    "amount": data.order_amount,
                    "currency": "INR",
                    "name": shopData.name,
                    "description": "Self-Service Print Job",
                    "order_id": data.order_id,
                    "handler": async function (response){
                        document.getElementById('upload-card').style.display = 'none';
                        document.getElementById('status-card').style.display = 'block';

                        const verifyRes = await fetch("/api/verify-payment", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({
                                job_id: data.job_id,
                                razorpay_order_id: response.razorpay_order_id,
                                razorpay_payment_id: response.razorpay_payment_id,
                                razorpay_signature: response.razorpay_signature
                            })
                        });

                        const verifyData = await verifyRes.json();
                        if (verifyData.status === "success") {
                            document.getElementById('status-spinner').style.display = 'none';
                            document.getElementById('status-title').innerText = "Payment Successful";
                            document.getElementById('status-desc').innerText = "Announcement made. Your document is printing now.";
                        } else {
                            document.getElementById('status-title').innerText = "Verification Failed";
                            document.getElementById('status-desc').innerText = "Contact shop owner.";
                        }
                    },
                    "modal": {
                        "ondismiss": function(){
                            btn.disabled = false;
                            btn.innerText = "Pay & Instant Print";
                        }
                    },
                    "theme": { "color": "#2563eb" }
                };

                const rzp = new Razorpay(options);
                rzp.open();
            } else {
                alert("Order initiation failed. Try again.");
                btn.disabled = false;
                btn.innerText = "Pay & Instant Print";
            }
        }
    </script>
</body>
</html>
"""

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,OPTIONS'
    return response

@app.route('/')
def home():
    shop_param = request.args.get('shop', 'default').lower()
    shop_info = SHOPS.get(shop_param, SHOPS['default'])
    return render_template_string(
        HTML_TEMPLATE,
        shop_id=shop_param,
        shop_data=shop_info,
        razorpay_key_id=RAZORPAY_KEY_ID
    )

@app.route('/api/submit-job', methods=['POST'])
def submit_job():
    shop_id = request.form.get('shop_id', 'default').lower()
    color_mode = request.form.get('color_mode', 'bw')
    copies = int(request.form.get('copies', 1))
    amount = float(request.form.get('amount', 2.0))
    file = request.files.get('file')

    job_id = str(uuid.uuid4())
    FILES_STORAGE[job_id] = {
        "filename": file.filename,
        "content": file.read()
    }

    # Razorpay expects amount in paise
    amount_in_paise = int(amount * 100)
    order_data = {
        "amount": amount_in_paise,
        "currency": "INR",
        "receipt": f"rcpt_{job_id[:8]}"
    }

    razorpay_order = razorpay_client.order.create(data=order_data)

    PRINT_JOBS.append({
        "job_id": job_id,
        "order_id": razorpay_order['id'],
        "shop_id": shop_id,
        "filename": file.filename,
        "color_mode": color_mode,
        "copies": copies,
        "amount": amount,
        "time": datetime.datetime.now().strftime("%I:%M %p"),
        "status": "pending_payment"
    })

    return jsonify({
        "status": "success",
        "job_id": job_id,
        "order_id": razorpay_order['id'],
        "order_amount": amount_in_paise
    })

@app.route('/api/verify-payment', methods=['POST'])
def verify_payment():
    data = request.json
    job_id = data.get('job_id')
    rzp_order_id = data.get('razorpay_order_id')
    rzp_payment_id = data.get('razorpay_payment_id')
    rzp_signature = data.get('razorpay_signature')

    try:
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': rzp_order_id,
            'razorpay_payment_id': rzp_payment_id,
            'razorpay_signature': rzp_signature
        })

        for job in PRINT_JOBS:
            if job['job_id'] == job_id:
                job['status'] = 'paid'
                return jsonify({"status": "success", "message": "Payment verified"})

        return jsonify({"status": "error", "message": "Job not found"}), 404

    except razorpay.errors.SignatureVerificationError:
        return jsonify({"status": "error", "message": "Signature verification failed"}), 400

@app.route('/api/get-pending-jobs')
def get_pending_jobs():
    shop_id = request.args.get('shop_id', 'default').lower()
    jobs = [j for j in PRINT_JOBS if j['shop_id'] == shop_id and j['status'] == 'paid']
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
