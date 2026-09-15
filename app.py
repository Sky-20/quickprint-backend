import os
import uuid
import datetime
import sqlite3
import razorpay
from flask import Flask, request, jsonify, render_template_string, Response

app = Flask(__name__)

RAZORPAY_KEY_ID = "rzp_live_TcLvuIP8zruBPY"
RAZORPAY_KEY_SECRET = "KOCsMWsd0g6Qk8SR2aZEDNV1"
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

DB_PATH = "/tmp/kiosk.db"
UPLOAD_DIR = "/tmp/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                order_id TEXT,
                shop_id TEXT,
                filename TEXT,
                copies INTEGER,
                amount REAL,
                status TEXT
            )
        """)
init_db()

SHOPS = {
    "default": {
        "name": "Dristi Online Center",
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
        .creator-badge { margin-top: 22px; padding-top: 12px; border-top: 1px dashed #cbd5e1; font-size: 12px; color: #64748b; }
    </style>
</head>
<body>
    <div class="card" id="upload-card">
        <h2>{{ shop_data.name }}</h2>
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
            <div class="bill-row"><span>Rate:</span><span id="bill-rate">₹{{ "%.2f"|format(shop_data.bw_rate) }}</span></div>
            <div class="total-row"><span>Total:</span><span id="bill-total" style="color: #2563eb;">₹{{ "%.2f"|format(shop_data.bw_rate) }}</span></div>
        </div>

        <button class="btn" id="pay-btn" onclick="startPayFlow()">Pay & Instant Print</button>
        <div class="creator-badge">Engineered & Built by Akash Verma</div>
    </div>

    <div class="card" id="status-card">
        <h2 style="color: #0f172a;" id="status-title">Verifying Payment...</h2>
        <p style="color: #64748b; font-size: 14px;" id="status-desc">Please wait while we confirm your print job.</p>
        <button class="btn" onclick="location.reload()" style="background: #0f172a; margin-top: 15px;">Print Another</button>
    </div>

    <script>
        const shopId = "{{ shop_id }}";
        const shopData = {
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
            btn.innerText = "Creating Order...";

            const total = calculateTotal();
            const formData = new FormData();
            formData.append("file", selectedFile);
            formData.append("shop_id", shopId);
            formData.append("copies", document.getElementById('copies').value);
            formData.append("amount", total);

            const res = await fetch("/api/submit-job", { method: "POST", body: formData });
            const data = await res.json();

            if (data.status === "success") {
                const options = {
                    "key": rzpKey,
                    "amount": data.order_amount,
                    "currency": "INR",
                    "name": "QuickPrint",
                    "order_id": data.order_id,
                    "prefill": {
                        "name": "Customer",
                        "email": "customer@quickprint.local",
                        "contact": "9999999999"
                    },
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
                            document.getElementById('status-title').innerText = "Payment Verified!";
                            document.getElementById('status-desc').innerText = "Print sent to counter printer.";
                        } else {
                            document.getElementById('status-title').innerText = "Payment Error";
                            document.getElementById('status-desc').innerText = verifyData.message || "Failed to verify signature.";
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
                new Razorpay(options).open();
            } else {
                alert("Failed to create order: " + (data.message || "Unknown error"));
                btn.disabled = false;
                btn.innerText = "Pay & Instant Print";
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    shop_param = request.args.get('shop', 'default').lower()
    shop_info = SHOPS.get(shop_param, SHOPS['default'])
    return render_template_string(HTML_TEMPLATE, shop_id=shop_param, shop_data=shop_info, razorpay_key_id=RAZORPAY_KEY_ID)

@app.route('/api/submit-job', methods=['POST'])
def submit_job():
    try:
        shop_id = request.form.get('shop_id', 'default').lower()
        copies = int(request.form.get('copies', 1))
        amount = float(request.form.get('amount', 2.0))
        file = request.files.get('file')

        job_id = str(uuid.uuid4())
        file_path = os.path.join(UPLOAD_DIR, f"{job_id}_{file.filename}")
        file.save(file_path)

        amount_in_paise = int(amount * 100)
        order_data = {"amount": amount_in_paise, "currency": "INR", "receipt": f"r_{job_id[:8]}"}
        razorpay_order = razorpay_client.order.create(data=order_data)

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (job_id, razorpay_order['id'], shop_id, file.filename, copies, amount, "pending_payment"))

        return jsonify({"status": "success", "job_id": job_id, "order_id": razorpay_order['id'], "order_amount": amount_in_paise})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/verify-payment', methods=['POST'])
def verify_payment():
    data = request.json or {}
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

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE jobs SET status = 'paid' WHERE job_id = ?", (job_id,))
            conn.commit()

        return jsonify({"status": "success", "message": "Payment verified and status updated to paid"})
    except Exception as e:
        print("Verification error:", e)
        return jsonify({"status": "error", "message": f"Verification error: {str(e)}"}), 400

@app.route('/api/razorpay-webhook', methods=['POST'])
def razorpay_webhook():
    payload = request.data.decode('utf-8')
    signature = request.headers.get('X-Razorpay-Signature')
    
    try:
        razorpay_client.utility.verify_webhook_signature(payload, signature, RAZORPAY_KEY_SECRET)
        event_data = request.json
        if event_data.get('event') in ['payment.captured', 'order.paid']:
            payload_entity = event_data.get('payload', {}).get('payment', {}).get('entity', {})
            order_id = payload_entity.get('order_id')
            if order_id:
                with sqlite3.connect(DB_PATH) as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE jobs SET status = 'paid' WHERE order_id = ?", (order_id,))
                    conn.commit()
                print(f"Webhook: Order {order_id} marked as PAID")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print("Webhook verification error:", e)
        return jsonify({"status": "failed", "error": str(e)}), 400

@app.route('/api/get-pending-jobs')
def get_pending_jobs():
    shop_id = request.args.get('shop_id', 'default').lower()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT job_id, filename, copies, amount FROM jobs WHERE shop_id = ? AND status = 'paid'", (shop_id,))
        rows = [dict(r) for r in cur.fetchall()]
    return jsonify(rows)

@app.route('/api/download-file/<job_id>')
def download_file(job_id):
    for fn in os.listdir(UPLOAD_DIR):
        if fn.startswith(f"{job_id}_"):
            path = os.path.join(UPLOAD_DIR, fn)
            with open(path, "rb") as f:
                data = f.read()
            original_name = fn.replace(f"{job_id}_", "", 1)
            return Response(data, headers={"Content-Disposition": f"attachment; filename={original_name}"})
    return "File Not Found", 404

@app.route('/api/complete-job/<job_id>', methods=['POST'])
def complete_job(job_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
        conn.commit()
    for fn in os.listdir(UPLOAD_DIR):
        if fn.startswith(f"{job_id}_"):
            try:
                os.remove(os.path.join(UPLOAD_DIR, fn))
            except Exception:
                pass
    return jsonify({"status": "completed"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
