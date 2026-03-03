import pika

credentials = pika.PlainCredentials('admin', 'admin123')

parameters = pika.ConnectionParameters(
    host='localhost',
    port=5672,
    credentials=credentials
)

connection = pika.BlockingConnection(parameters)
print("Connected successfully!")
connection.close()