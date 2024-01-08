import os
from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_bcrypt import Bcrypt
from flask_mail import Mail, Message
import uuid
from twilio.rest import Client
from dotenv import load_dotenv
import urllib.request
from flask_cors import CORS
load_dotenv()


app = Flask(__name__)
CORS(app)
app.config['MONGO_URI'] = os.getenv('MONGO_URI')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USERNAME'] = 'viperbale.db@gmail.com'
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_USE_SSL'] = True
app.config['TWILIO_ACCOUNT_SID'] = os.getenv('TWILIO_ACCOUNT_SID')
app.config['TWILIO_AUTH_TOKEN'] = os.getenv('TWILIO_AUTH_TOKEN')
app.config['ESP_URL'] = os.getenv('ESP_URL')
mongo = PyMongo(app)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)
mail = Mail(app)
twilio_client = Client(
    app.config['TWILIO_ACCOUNT_SID'], app.config['TWILIO_AUTH_TOKEN'])


class User:
    def __init__(self, id, first_name, last_name, email, phone, password, land=[]):
        self.id = id
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.phone = phone
        self.password = password
        self.land = land


def generate_unique_id(first_name, last_name):
    first_name = first_name.lower()
    last_name = last_name.lower()

    first_3 = first_name[:3]
    last_3 = last_name[:3]

    if len(first_3) < 3:
        first_3 = first_3.ljust(3, 'x')
    if len(last_3) < 3:
        last_3 = last_3.ljust(3, 'x')

    unique_string = str(uuid.uuid4().hex)[:8]
    generated_id = f"{first_3}{last_3}{unique_string}"

    return generated_id


def send_welcome_email(user_email, user_name):
    subject = 'Welcome to Agro-Smart-Hub!'

    # HTML content for the email
    html_body = """
    <!DOCTYPE html>
    <html>
      <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <link href="" rel="stylesheet" />
        <title>Email Template</title>
      </head>
      <body>
        <p>Subject: Welcome Aboard! 🌱🤝</p>
        <p><br /></p>
        <p>Dear {user_name},</p>
        <p><br /></p>
        <p>Thrilled to have you as part of the AgroSmartHub community!</p>
        <p><br /></p>
        <p>🌾 Next Steps: Our dedicated team will be reaching out to you soon.</p>
        <p>
          💡 Personalized Support: Get ready for tailored assistance to maximize
          your farming success.
        </p>
        <p><br /></p>
        <p>
          Your journey with AgroSmartHub is about to blossom. If you have any
          questions or need assistance, our team is here to help. Stay tuned for a
          call from our team!
        </p>
        <p><br /></p>
        <p>Best,</p>
        <p>[SUPPORT Name]</p>
        <p>AgroSmartHub Team</p>
      </body>
    </html>
    """
    msg = Message(subject, sender='viperbale.db@gmail.com',
                  recipients=[user_email])
    msg.body = "Welcome to Agro-Smart-Hub! We will contact you soon for the installation of the machine."

    msg.html = html_body.format(user_name=user_name)

    mail.send(msg)


def send_whatsapp_message(to):
    body = 'Thank you for registering to Agro-Smart-Hub. We will contact you soon for the installation of the machine.'
    twilio_client.messages.create(
        from_='whatsapp:+14155238886',
        body=body,
        to='whatsapp:+917980614349'
    )


@app.route('/get-users', methods=['GET'])
def get_users():
    users = mongo.db.users.find()
    output = []
    for user in users:
        output.append({'id': user['id'], 'first_name': user['first_name'],
                      'last_name': user['last_name'], 'email': user['email'], 'phone': user['phone'], 'land': user['land']})
    return jsonify({'users': output})


@app.route('/create-users', methods=['POST'])
def add_user():
    if not all(field in request.json for field in ['first_name', 'last_name', 'email', 'phone', 'password']):
        return jsonify({'message': 'Fields are missing'}), 404

    generated_id = generate_unique_id(
        request.json['first_name'], request.json['last_name'])

    existing_user = mongo.db.users.find_one({'email': request.json['email']})
    if existing_user:
        return jsonify({'message': 'User already exists'}), 400

    hashed_password = bcrypt.generate_password_hash(
        request.json['password']).decode('utf-8')

    user = User(generated_id, request.json['first_name'],
                request.json['last_name'], request.json['email'], request.json['phone'], hashed_password, request.json['land'])
    mongo.db.users.insert_one(user.__dict__)

    # Send welcome email
    send_welcome_email(request.json['email'], request.json['first_name'])

    # send welcome whatsapp message
    send_whatsapp_message(request.json['phone'])

    return jsonify({'message': 'User added successfully'})


@app.route('/login', methods=['POST'])
def login():
    if not all(field in request.json for field in ['email', 'password']):
        return jsonify({'message': 'Fields are missing'}), 404

    user = mongo.db.users.find_one({'email': request.json['email']})
    if not user or not bcrypt.check_password_hash(user['password'], request.json['password']):
        return jsonify({'message': 'Invalid email or password'}), 401

    access_token = create_access_token(identity=user['id'])
    return jsonify(access_token=access_token)


@app.route('/update-user/<user_id>', methods=['PUT'])
def update_user(user_id):

    users_collection = mongo.db.users

    user = users_collection.find_one({'id': user_id})

    if user:

        updated_details = request.json

        for key, value in updated_details.items():
            if key in user:
                user[key] = value

        users_collection.update_one({'id': user_id}, {'$set': user})

        return jsonify({'message': 'User details updated successfully'})
    else:
        return jsonify({'message': 'User not found'}), 404


@app.route('/get-user/<user_id>', methods=['GET'])
def get_user(user_id):

    users_collection = mongo.db.users
    user = users_collection.find_one({'id': user_id})

    if user:
        user_data = {
            'id': user['id'],
            'first_name': user['first_name'],
            'last_name': user['last_name'],
            'email': user['email'],
            'phone': user['phone'],
            'password': user['password'],
            'land': user['land']
        }

        return jsonify({'user': user_data})
    else:
        return jsonify({'message': 'User not found'}), 404


@app.route('/delete-user/<user_id>', methods=['DELETE'])
def delete_user(user_id):

    users_collection = mongo.db.users

    user = users_collection.find_one({'id': user_id})

    if user:

        users_collection.delete_one({'id': user_id})
        return jsonify({'message': 'User deleted successfully'})
    else:
        return jsonify({'message': 'User not found'}), 404


@app.route('/get-sensor-data', methods=['GET'])
def get_sensor_data():
    global sensor_data
    n = urllib.request.urlopen(app.config['ESP_URL']).read()
    n = n.decode("utf-8")
    sensor_data = n.split()
    return jsonify({"data": "Moisture Value: {}".format(sensor_data[0])}), 200


@app.route('/start-motor', methods=['POST'])
def start_motor():
    pump_control = request.json['pump_control']
    print(pump_control)
    if pump_control == "YES":
        urllib.request.urlopen(app.config['ESP_URL'] + "control?value=1")
        print("Pump turned ON.")
    elif pump_control == "NO":
        urllib.request.urlopen(app.config['ESP_URL'] + "control?value=0")
        print("Pump turned OFF.")
    else:
        print("Invalid input. Please enterYESorNO.")

    return jsonify({
        "success": True,
        "message": "Motor activated successfully"
    })


@app.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    current_user = get_jwt_identity()
    return jsonify(logged_in_as=current_user), 200


if __name__ == '__main__':
    app.run(debug=True)
