import os
import uuid
import razorpay
from flask import Flask, request, jsonify, render_template_string, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ORDERS_DIR = os.path.join(BASE_DIR, "orders")
TEMP_DIR = os.path.join(BASE_DIR, "temp_uploads")
os.makedirs(ORDERS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# Razorpay Credentials
RAZORPAY_KEY_ID = "rzp_test_TS2Vq0G1hlAz2x"
RAZORPAY_KEY_SECRET = "1Ur7xBBw5LyO1d2H3RqSWVho"
client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# Active Shops Database
SHOPS_DB = {
    "shop_101": {
        "name": "Print Catalyst Spot",
        "is_active": True,
        "rate_bw": 2,
        "rate_color": 10
    }
}
PRINT_QUEUE = {}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ shop.name }}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.min.js"></script>
</head>
<body class="bg-gray-100 min-h-screen flex items-center justify-center p-4">
    <div class="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 border border-gray-100">
        <div class="text-center mb-6">
            <h1 class="text-2xl font-bold text-gray-800">{{ shop.name }}</h1>
            <p class="text-xs text-gray-500 mt-1">Smart Document Printing</p>
        </div>

        <div id="stepUpload" class="space-y-4">
            <div class="border-2 border-dashed border-blue-400 rounded-xl p-5 text-center bg-blue-50/50 hover:bg-blue-50 transition cursor-pointer">
                <input type="file" id="docFile" accept=".pdf,.txt,.png,.jpg,.jpeg" required class="hidden" onchange="handleFileSelect()">
                <label for="docFile" class="cursor-pointer block">
                    <svg class="w-10 h-10 mx-auto text-blue-500 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
                    </svg>
                    <span id="fileLabel" class="text-sm font-semibold text-blue-600">Tap to Select Document</span>
                    <p id="pageInfo" class="text-xs text-gray-500 mt-1">PDF, Images, TXT</p>
                </label>
            </div>

            <div class="grid grid-cols-2 gap-3 text-sm">
                <div>
                    <label class="block font-medium text-gray-700 mb-1">Color Mode</label>
                    <select id="colorMode" class="w-full border rounded-lg p-2.5 bg-gray-50 focus:ring-2 focus:ring-blue-500">
                        <option value="bw">B & W (₹{{ shop.rate_bw }}/page)</option>
                        <option value="color">Color (₹{{ shop.rate_color }}/page)</option>
                    </select>
                </div>
                <div>
                    <label class="block font-medium text-gray-700 mb-1">Copies</label>
                    <input type="number" id="copies" value="1" min="1" max="50" class="w-full border rounded-lg p-2.5 bg-gray-50">
                </div>
            </div>

            <div class="bg-gray-50 p-3.5 rounded-xl border border-gray-200 text-xs space-y-1 text-gray-600">
                <div class="flex justify-between">
                    <span>Total Pages:</span>
                    <span id="summaryPages" class="font-semibold text-gray-800">1</span>
                </div>
                <div class="flex justify-between">
                    <span>Rate per Page:</span>
                    <span id="summaryRate" class="font-semibold text-gray-800">₹{{ shop.rate_bw }}.00</span>
                </div>
                <div class="border-t pt-1 flex justify-between text-sm font-bold text-gray-900">
                    <span>Grand Total:</span>
                    <span id="priceDisplay" class="text-blue-600 font-extrabold">₹{{ shop.rate_bw }}.00</span>
                </div>
            </div>

            <button type="button" onclick="startPaymentFlow()" id="payBtn" class="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-xl shadow-lg shadow-blue-500/30 transition duration-200">
                Proceed to Pay & Print
            </button>
        </div>

        <div id="statusMsg" class="mt-4 text-center text-sm font-medium hidden"></div>
    </div>

    <script>
        pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.worker.min.js';
        const fileInput = document.getElementById('docFile');
        const fileLabel = document.getElementById('fileLabel');
        const pageInfo = document.getElementById('pageInfo');
        const copiesInput = document.getElementById('copies');
        const colorMode = document.getElementById('colorMode');
        const summaryPages = document.getElementById('summaryPages');
        const summaryRate = document.getElementById('summaryRate');
        const priceDisplay = document.getElementById('priceDisplay');
        const payBtn = document.getElementById('payBtn');
        const statusMsg = document.getElementById('statusMsg');

        const rateBW = {{ shop.rate_bw }};
        const rateColor = {{ shop.rate_color }};
        const shopId = "{{ shop_id }}";

        let detectedPages = 1;
        let currentTotal = rateBW;

        async function handleFileSelect() {
            if (!fileInput.files.length) return;
            const file = fileInput.files[0];
            fileLabel.innerText = file.name;

            if (file.type === 'application/pdf') {
                pageInfo.innerText = "Analyzing pages...";
                try {
                    const arrayBuffer = await file.arrayBuffer();
                    const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
                    detectedPages = pdf.numPages;
                    pageInfo.innerText = `Detected ${detectedPages} Page(s)`;
                } catch (e) {
                    detectedPages = 1;
                    pageInfo.innerText = "PDF ready";
                }
            } else {
                detectedPages = 1;
                pageInfo.innerText = "Single Page Image/Doc";
            }
            calculatePrice();
        }

        function calculatePrice() {
            const rate = colorMode.value === 'bw' ? rateBW : rateColor;
            const copies = parseInt(copiesInput.value) || 1;
            currentTotal = detectedPages * copies * rate;

            summaryPages.innerText = `${detectedPages} page(s) × ${copies} cop(ies)`;
            summaryRate.innerText = `₹${rate}.00`;
            priceDisplay.innerText = `₹${currentTotal.toFixed(2)}`;
        }

        copiesInput.addEventListener('input', calculatePrice);
        colorMode.addEventListener('change', calculatePrice);

        async function startPaymentFlow() {
            if (!fileInput.files.length) {
                alert("Please select a file to print first!");
                return;
            }

            payBtn.disabled = true;
            payBtn.innerText = "Creating Order...";
            statusMsg.className = "mt-4 text-center text-sm font-medium text-blue-600";
            statusMsg.innerText = "Preparing payment...";
            statusMsg.classList.remove('hidden');

            const formData = new FormData();
            formData.append('file', fileInput.files[0]);
            formData.append('amount', currentTotal);
            formData.append('shop_id', shopId);

            try {
                const res = await fetch('/create-order', { method: 'POST', body: formData });
                const orderData = await res.json();
                if (orderData.error) throw new Error(orderData.error);

                const options = {
                    "key": orderData.razorpay_key,
                    "amount": orderData.amount,
                    "currency": "INR",
                    "name": "{{ shop.name }}",
                    "description": "Document Print Charge",
                    "order_id": orderData.order_id,
                    "handler": async function (response) {
                        statusMsg.innerText = "Verifying payment...";
                        const verifyRes = await fetch('/verify-payment', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                razorpay_order_id: response.razorpay_order_id,
                                razorpay_payment_id: response.razorpay_payment_id,
                                razorpay_signature: response.razorpay_signature,
                                job_id: orderData.job_id,
                                filename: orderData.filename,
                                shop_id: shopId
                            })
                        });

                        const verifyData = await verifyRes.json();
                        if (verifyData.success) {
                            statusMsg.className = "mt-4 text-center text-sm font-medium text-green-600";
                            statusMsg.innerText = "✓ Payment Verified! Sent to printer.";
                        } else {
                            statusMsg.className = "mt-4 text-center text-sm font-medium text-red-600";
                            statusMsg.innerText = "Payment verification failed.";
                        }
                        payBtn.disabled = false;
                        payBtn.innerText = "Proceed to Pay & Print";
                    },
                    "modal": {
                        "ondismiss": function() {
                            payBtn.disabled = false;
                            payBtn.innerText = "Proceed to Pay & Print";
                            statusMsg.className = "mt-4 text-center text-sm font-medium text-gray-500";
                            statusMsg.innerText = "Payment cancelled";
                        }
                    },
                    "theme": { "color": "#2563eb" }
                };
                new Razorpay(options).open();
            } catch (err) {
                statusMsg.className = "mt-4 text-center text-sm font-medium text-red-600";
                statusMsg.innerText = "Error: " + err.message;
                payBtn.disabled = false;
                payBtn.innerText = "Proceed to Pay & Print";
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    shop_id = request.args.get('shop_id', 'shop_101')
    shop = SHOPS_DB.get(shop_id)
    if not shop or not shop.get("is_active"):
        return "<h2 style='text-align:center;margin-top:50px;'>Print Point is currently unavailable.</h2>", 403
    return render_template_string(HTML_TEMPLATE, shop=shop, shop_id=shop_id)

@app.route('/create-order', methods=['POST'])
def create_order():
    try:
        uploaded_file = request.files.get('file')
        amount_str = request.form.get('amount', '2')
        shop_id = request.form.get('shop_id', 'shop_101')

        if not uploaded_file:
            return jsonify({'error': 'No file uploaded'}), 400

        job_id = str(uuid.uuid4())[:8]
        filename = f"{job_id}_{uploaded_file.filename}"
        temp_path = os.path.join(TEMP_DIR, filename)
        uploaded_file.save(temp_path)

        amount_in_paise = int(float(amount_str) * 100)
        razorpay_order = client.order.create({
            "amount": amount_in_paise,
            "currency": "INR",
            "payment_capture": "1"
        })

        return jsonify({
            'order_id': razorpay_order['id'],
            'amount': amount_in_paise,
            'job_id': job_id,
            'filename': filename,
            'razorpay_key': RAZORPAY_KEY_ID
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/verify-payment', methods=['POST'])
def verify_payment():
    data = request.get_json() or {}
    shop_id = data.get('shop_id', 'shop_101')
    job_id = data.get('job_id')
    filename = data.get('filename')

    temp_path = os.path.join(TEMP_DIR, filename)
    final_path = os.path.join(ORDERS_DIR, filename)

    try:
        client.utility.verify_payment_signature({
            'razorpay_order_id': data.get('razorpay_order_id'),
            'razorpay_payment_id': data.get('razorpay_payment_id'),
            'razorpay_signature': data.get('razorpay_signature')
        })

        if os.path.exists(temp_path):
            os.rename(temp_path, final_path)

        if shop_id not in PRINT_QUEUE:
            PRINT_QUEUE[shop_id] = []

        host_url = request.host_url.rstrip('/')
        PRINT_QUEUE[shop_id].append({
            "job_id": job_id,
            "filename": filename,
            "file_url": f"{host_url}/download-file/{filename}"
        })

        return jsonify({'success': True})
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/download-file/<filename>')
def download_file(filename):
    return send_from_directory(ORDERS_DIR, filename)

@app.route('/api/get-pending-prints/<shop_id>', methods=['GET'])
def get_pending_prints(shop_id):
    jobs = PRINT_QUEUE.get(shop_id, [])
    return jsonify({'jobs': jobs})

@app.route('/api/complete-print/<shop_id>/<job_id>', methods=['POST'])
def complete_print(shop_id, job_id):
    if shop_id in PRINT_QUEUE:
        PRINT_QUEUE[shop_id] = [j for j in PRINT_QUEUE[shop_id] if j['job_id'] != job_id]
    
    for f in os.listdir(ORDERS_DIR):
        if f.startswith(job_id):
            try:
                os.remove(os.path.join(ORDERS_DIR, f))
            except:
                pass
    return jsonify({'status': 'cleaned'})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)