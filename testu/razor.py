import razorpay
import time
import requests

# Razorpay API Credentials
KEY_ID = "rzp_live_whGnMZeGzeGe2l"
KEY_SECRET = "QBzrGMNofkapxcHZfd7nt160"

# Initialize Razorpay Client
client = razorpay.Client(auth=(KEY_ID, KEY_SECRET))

# Set App Details (Optional)
client.set_app_details({"title": "MyApp", "version": "1.0"})

# Generate expiry timestamp (current time + 15 minutes)
expiry_time = int(time.time()) + 900  # 900 seconds = 15 minutes

# Create QR Code
qr_code = client.qrcode.create({
    "type": "upi_qr",
    "name": "One-time ₹10 Payment",
    "usage": "single_use",
    "fixed_amount": True,
    "payment_amount": 1000,  # Amount in paise (₹10 = 1000 paise)
    "description": "One-time payment of ₹10",
    "close_by": expiry_time,
    "notes": {"purpose": "One-time ₹10 payment"}
})

# Get QR Code ID and Image URL
qr_id = qr_code["id"]
qr_image_url = qr_code["image_url"]

print(f"QR Code ID: {qr_id}")
print(f"QR Code Image URL: {qr_image_url}")

# Download the QR code image
qr_image_response = requests.get(qr_image_url)
if qr_image_response.status_code == 200:
    with open("razorpay_qr.png", "wb") as file:
        file.write(qr_image_response.content)
    print("QR Code downloaded successfully as 'razorpay_qr.png'.")
else:
    print("Failed to download QR code image.")

# Start checking payment status
print("Waiting for payment...")

# Store the time when QR was created
start_time = time.time()

while True:
    try:
        # Fetch QR code details
        qr_status = client.qrcode.fetch(qr_id)

        # Get payment amount received
        amount_received = qr_status["payments_amount_received"]  # Amount in paise
        status = qr_status["status"]

        if amount_received >= 1000:
            print(f"Payment of ₹{amount_received / 100} received successfully!")
            break

        # Check if 15 minutes have passed
        if time.time() - start_time >= 900:  # 900 seconds = 15 minutes
            print("15 minutes passed. Closing the QR code...")
            client.qrcode.close(qr_id)
            print("QR Code closed.")
            break

        time.sleep(5)  # Wait for 5 seconds before checking again

    except Exception as e:
        print("Error checking payment status:", e)
        break
