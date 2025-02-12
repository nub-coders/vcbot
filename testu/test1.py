import base64

# Python code to be encoded
code = 'print("Hello World")'

# Encoding the code in base64
encoded_code = base64.b64encode(code.encode('utf-8')).decode('utf-8')

print(encoded_code)  # Just to check the encoded output
