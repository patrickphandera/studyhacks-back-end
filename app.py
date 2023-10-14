from flask import Flask, jsonify, request, session, redirect, url_for, render_template, send_file
from pymongo import MongoClient
from bson import ObjectId
from waitress import serve
from datetime import datetime, timedelta
from flask_cors import CORS
import pytesseract
from functools import wraps
from PIL import Image
import uuid
import os
revoked_tokens = []
import PyPDF2
from time import sleep
from flask_bcrypt import Bcrypt

import openai
from dotenv import load_dotenv
import jwt
token = "your_jwt_token"  # Replace with your JWT
secret_key = "your_secret_key"
algorithm = "HS256"
exp= datetime.utcnow() + timedelta(hours=2)
load_dotenv()

GPT_API = os.getenv('GPT_API')
backend_url = "https://api-docs-studyhacks-v1.onrender.com"
openai.api_key = GPT_API

app = Flask(__name__)
CORS(app, supports_credentials=True)
app.secret_key ="srevvhhhff"
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')
bcrypt = Bcrypt(app)


os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

client = MongoClient("mongodb+srv://userxyz:userxyz@cluster0.5be8y.mongodb.net/?retryWrites=true&w=majority")
db = client["studyhacks"]
chats_collection = db["chats"]
users_collection = db["users"]
content_collection = db["documents"]
sammaries_collection = db["summaries"]
import functools
from flask import jsonify


# GETTING DOCUMENTATION 
@app.route('/')
def index():
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], "studyhacks-docs.pdf")
    return send_file(file_path)

# REGISTERATING A USER
@app.route('/register', methods=['POST'])
def register_user():
    data = request.get_json()
    email = data.get('email')
    name = data.get('name')
    role = data.get('role')
    profile_complete = data.get('profile_complete')
    profile_picture = data.get("profile_picture")
    password = data.get('password')
    gender = data.get("gender")
    institution = data.get("institution")
    mobile = data.get("mobile")
    country = data.get("country")
    data['timestamp'] = str(datetime.now())
    if not email or not password:
        return jsonify({'msg': 'Email and password are required'}), 400

    existing_user = users_collection.find_one({'email': email})
    if existing_user:
        return jsonify({'msg': 'User already exists'}), 400

    _id = str(ObjectId())

    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

    user = {
        '_id': _id,
        "name": name,
        "mobile": mobile,
        'email': email,
        "role": role,
        'password': hashed_password,
        "profile_complete": profile_complete,
        "profile_picture": profile_picture,
        "country": country,
        "gender": gender,
        "institution": institution
    }

    users_collection.insert_one(user)

    return jsonify({'msg': 'User registered successfully'}), 201


# LOGINING IN A USER
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'msg': 'Email and password are required'}), 400

    user = users_collection.find_one({'email': email})

    if not user or not bcrypt.check_password_hash(user['password'], password):
        return jsonify({'msg': 'Invalid credentials'}), 401
    token =get_token(user["_id"])
    return jsonify({'msg': 'Login successful', 'access_token': token, 'user': user}), 200

# GETTING USERS
@app.route('/users', methods=['GET'])
def get_all_users():
    res= authorise_request(request)
    if(res=="expired"):
        return jsonify({"message": "Token expired"}), 403
    elif (res=="invalid"):
        return jsonify({"message": "Token is invalid"}),403
    elif(res=="not found"):
        return jsonify({"message": "Token not found"}),403
    elif(res=="revoked"):
        return jsonify({"message": "Token revoked"}),403
    else:
        users = list(users_collection.find())
        for user in users:
            user['_id'] = str(user['_id'])
        return jsonify(users), 200

# GETTING A USER
@app.route('/users/<string:user_id>', methods=['GET'])
def get_single_user(user_id):
    res= authorise_request(request)
    if(res=="expired"):
        return jsonify({"message": "Token expired"}), 403
    elif (res=="invalid"):
        return jsonify({"message": "Token is invalid"}),403
    elif(res=="not found"):
        return jsonify({"message": "Token not found"}),403
    else:
        user_id=res["id"]
        user = users_collection.find_one({"_id": user_id})

        if user is None:
            return jsonify({"message": "User not found"}), 404

        user['_id'] = str(user['_id'])

        return jsonify(user), 200

# LOGGING OUT USER
@app.route('/logout', methods=['POST'])
def logout():
    res= authorise_request(request)
    if(res=="expired"):
        return jsonify({"message": "Token expired"}), 403
    elif (res=="invalid"):
        return jsonify({"message": "Token is invalid"}),403
    elif(res=="not found"):
        return jsonify({"message": "Token not found"}),403
    else:
        if(revoke_token(res)=="revoked"):
            return jsonify({'msg': 'Logged out successfully'}), 200
        else:
            return jsonify({'msg': 'Logged out not successful'}), 200
        
        
# @app.route('/users/<string:_id>', methods=['GET'])
# def get_user(_id):
#     res= authorise_request(request)
#     if(res=="expired"):
#         return jsonify({"message": "Token expired"}), 403
#     elif (res=="invalid"):
#         return jsonify({"message": "Token is invalid"}),403
#     elif(res=="not found"):
#         return jsonify({"message": "Token not found"}),403
#     elif(res=="revoked"):
#         return jsonify({"message": "Token is revoked"}),403
#     else:
#         user = users_collection.find_one({'_id': _id})
#         if user:
#             user['_id'] = str(user['_id'])
#             return jsonify(user), 200
#         else:
#             return jsonify({'message': 'User not found'}), 404


# CHANGE pASWORD
@app.route('/change_password', methods=['POST'])
def change_password():
    res= authorise_request(request)
    if(res=="expired"):
        return jsonify({"message": "Token expired"}), 403
    elif (res=="invalid"):
        return jsonify({"message": "Token is invalid"}),403
    elif(res=="not found"):
        return jsonify({"message": "Token not found"}),403
    elif(res=="revoked"):
        return jsonify({"message": "Token is revoked"}),403
    else:
        user_id=res["id"]
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        user = users_collection.find_one({'_id': user_id})

        if not user or not bcrypt.check_password_hash(user['password'], current_password):
            return jsonify({'msg': 'Current password is incorrect'}), 401

        hashed_new_password = bcrypt.generate_password_hash(new_password).decode('utf-8')

        users_collection.update_one({'_id': id}, {'$set': {'password': hashed_new_password}})

        return jsonify({'msg': 'Password updated successfully'}), 200


# UpLOAD pDF
@app.route('/pdfs', methods=['POST'])
def upload_pdf():
    res= authorise_request(request)
    if(res=="expired"):
        return jsonify({"message": "Token expired"}), 403
    elif (res=="invalid"):
        return jsonify({"message": "Token is invalid"}),403
    elif(res=="not found"):
        return jsonify({"message": "Token not found"}),403
    elif(res=="revoked"):
        return jsonify({"message": "Token is revoked"}),403
    else:
        user_id=res["id"]
        if 'file' not in request.files:
            return "No file part", 400
        
        file = request.files['file']
        
        if file.filename == '':
            return "No selected file", 400
        original_name=file.filename
        unique_id = uuid.uuid4()
        _id = str(ObjectId())
        pdf_loc=os.path.join(app.config['UPLOAD_FOLDER'],  str(unique_id)+".pdf")
        file.save(pdf_loc)
        extracted_text = extract_text_from_pdf(pdf_loc)
        data = {}
        data['user_id']=user_id
        data['type_']='pdf'
        data["extracted_text"]=extracted_text
        data["name"]=str(unique_id)+".pdf"
        data["original_name"]=original_name
        data["chat_ids"]=[]
        data["_id"]=_id
        data["path"]=backend_url+'/files/download/'+_id
        data['timestamp']=str(datetime.now())
        document = content_collection.insert_one(data)
        return jsonify({"msg": "Document processed successfully","id":document.inserted_id}),201


# UpLOADING IMAGES
@app.route('/images', methods=['POST'])
def upload_image():
    res= authorise_request(request)
    if(res=="expired"):
        return jsonify({"message": "Token expired"}), 403
    elif (res=="invalid"):
        return jsonify({"message": "Token is invalid"}),403
    elif(res=="not found"):
        return jsonify({"message": "Token not found"}),403
    elif(res=="revoked"):
        return jsonify({"message": "Token is revoked"}),403
    else:
        user_id=res["id"]
        if 'file' not in request.files:
            return "No file part", 400
        
        file = request.files['file']
        
        if file.filename == '':
            return "No selected file", 400
        
        unique_id = uuid.uuid4()
        _id = str(ObjectId())
        pdf_loc=os.path.join(app.config['UPLOAD_FOLDER'],  str(unique_id)+".pdf")
        file.save(pdf_loc)
        extracted_text = extract_text_from_pdf(pdf_loc)
        data = {}
        data['user_id']=user_id
        data['type_']='pdf'
        data["extracted_text"]=extracted_text
        data["name"]=str(unique_id)+".pdf"
        data["chat_ids"]=[]
        data["_id"]=_id
        data["path"]=backend_url+'/files/download/'+_id
        data['timestamp']=str(datetime.now())
        document = content_collection.insert_one(data)
        return jsonify({"msg": "Document processed successfully"}),201

# UpLOADING TEXT documents
@app.route('/text', methods=['POST'])
def upload_text():
    res= authorise_request(request)
    if(res=="expired"):
        return jsonify({"message": "Token expired"}), 403
    elif (res=="invalid"):
        return jsonify({"message": "Token is invalid"}),403
    elif(res=="not found"):
        return jsonify({"message": "Token not found"}),403
    elif(res=="revoked"):
        return jsonify({"message": "Token is revoked"}),403
    else:
        user_id=res["id"]
        data = request.get_json()
        text = data['text']
        unique_id = uuid.uuid4()
        _id = str(ObjectId())
        data = {}  
        answer1 = f'{text[:25]}...'
        data['user_id'] = user_id
        data['type_'] = 'text'
        data["extracted_text"] = text
        data["name"] = ''
        data["title"] = answer1
        data["chat_ids"] = []
        data["_id"] = _id
        data["path"] = ""
        data['timestamp'] = str(datetime.now())
        document = content_collection.insert_one(data)
        return jsonify({"msg": "Text processed successfully"}), 201

# retrieve all text documents
@app.route('/text', methods=['GET'])
def get_files():
    res= authorise_request(request)
    if(res=="expired"):
        return jsonify({"message": "Token expired"}), 403
    elif (res=="invalid"):
        return jsonify({"message": "Token is invalid"}),403
    elif(res=="not found"):
        return jsonify({"message": "Token not found"}),403
    elif(res=="revoked"):
        return jsonify({"message": "Token is revoked"}),403
    else:
        user_id=res["id"]
        documents_list = list(content_collection.find({"user_id":user_id, "type_": "text"}))
        return jsonify(documents_list), 200
    
    # retrive one text document
@app.route('/text/<text_id>', methods=['GET'])
def get_text(text_id):
    res = authorise_request(request)
    if res == "expired":
        return jsonify({"message": "Token expired"}), 403
    elif res == "invalid":
        return jsonify({"message": "Token is invalid"}), 403
    elif res == "not found":
        return jsonify({"message": "Token not found"}), 403
    elif res == "revoked":
        return jsonify({"message": "Token is revoked"}), 403
    else:
        user_id=res["id"]
        document = content_collection.find_one({"_id": text_id,"user_id":user_id, "type_": "text"})
        if document:
            return jsonify(document), 200
        else:
            return jsonify({"message": "Text document not found"}), 404

# retrive all psf documents  
@app.route('/pdfs', methods=['GET'])
def get_pdfs():
    res= authorise_request(request)
    if(res=="expired"):
        return jsonify({"message": "Token expired"}), 403
    elif (res=="invalid"):
        return jsonify({"message": "Token is invalid"}),403
    elif(res=="not found"):
        return jsonify({"message": "Token not found"}),403
    elif(res=="revoked"):
        return jsonify({"message": "Token is revoked"}),403
    else:
        user_id=res["id"]
        documents_list = list(content_collection.find({"user_id":user_id,"type_": "pdf"}))
        return jsonify(documents_list), 200

# retrieve one pdf document 
@app.route('/pdfs/<pdf_id>', methods=['GET'])
def get_pdf(pdf_id):
    res = authorise_request(request)
    if res == "expired":
        return jsonify({"message": "Token expired"}), 403
    elif res == "invalid":
        return jsonify({"message": "Token is invalid"}), 403
    elif res == "not found":
        return jsonify({"message": "Token not found"}), 403
    elif res == "revoked":
        return jsonify({"message": "Token is revoked"}), 403
    else:
        print(res)
        document = content_collection.find_one({"_id": pdf_id, "type_": "pdf"})
        if document:
            return jsonify(document), 200
        else:
            return jsonify({"message": "PDF not found"}), 404
from flask import request


# delete one pdf document
@app.route('/pdfs/<pdf_id>', methods=['DELETE'])
def delete_pdf(pdf_id):
    res = authorise_request(request)
    if res == "expired":
        return jsonify({"message": "Token expired"}), 403
    elif res == "invalid":
        return jsonify({"message": "Token is invalid"}), 403
    elif res == "not found":
        return jsonify({"message": "Token not found"}), 403
    elif res == "revoked":
        return jsonify({"message": "Token is revoked"}), 403
    else:
        # Add code here to delete the PDF document with the specified pdf_id
        result = content_collection.delete_one({"_id": pdf_id, "type_": "pdf"})
        if result.deleted_count > 0:
            return jsonify({"message": "PDF document deleted successfully"}), 200
        else:
            return jsonify({"message": "PDF not found for deletion"}), 404

#  get all imag documents 
@app.route('/images', methods=['GET'])
def get_images():
    res= authorise_request(request)
    if(res=="expired"):
        return jsonify({"message": "Token expired"}), 403
    elif (res=="invalid"):
        return jsonify({"message": "Token is invalid"}),403
    elif(res=="not found"):
        return jsonify({"message": "Token not found"}),403
    elif(res=="revoked"):
        return jsonify({"message": "Token is revoked"}),403
    else:
        user_id=res["id"]
        documents_list = list(content_collection.find({"user_id":user_id,"type_": "image"}))
        return jsonify(documents_list), 200

# getting all documents
@app.route('/pdf_images_text', methods=['GET'])
def get_all_contents():
    res= authorise_request(request)
    if(res=="expired"):
        return jsonify({"message": "Token expired"}), 403
    elif (res=="invalid"):
        return jsonify({"message": "Token is invalid"}),403
    elif(res=="not found"):
        return jsonify({"message": "Token not found"}),403
    elif(res=="revoked"):
        return jsonify({"message": "Token is revoked"}),403
    else:
        documents_list = list(content_collection.find({"user_id":res["id"]}))
        return jsonify(documents_list), 200

# download documents
@app.route('/files/download/<_id>', methods=['GET'])
def download_file(_id):
    document = content_collection.find_one({"_id": _id})
    if document:
        pdf_name = document["name"]
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_name)
        return send_file(file_path)
    else:
        return jsonify({"msg": "File not found"}), 404

# create a chat message
@app.route("/chats/<string:pdf_id>", methods=["POST"])
def create_chat(pdf_id):
    res= authorise_request(request)
    if(res=="expired"):
        return jsonify({"message": "Token expired"}), 403
    elif (res=="invalid"):
        return jsonify({"message": "Token is invalid"}),403
    elif(res=="not found"):
        return jsonify({"message": "Token not found"}),403
    elif(res=="revoked"):
        return jsonify({"message": "Token is revoked"}),403
    else:
        user_id=res["id"]
        data = request.get_json()
        print(data)
        question = data["question"]
        document = content_collection.find_one({"_id": pdf_id})
        context = document['extracted_text']
        response = openai.Completion.create(
            engine="text-davinci-002",
            prompt=f"Context: {context}\nQuestion: {question}\nAnswer:",
            max_tokens=50
        )
        _id = str(ObjectId())
        answer = response.choices[0].text.strip()
        answer1 = f'{context[:25]}...'
        answer = response.choices[0].text.strip()
        data['answer'] = answer
        data['title'] = answer1
        data['question'] = question
        data["pdf_id"] = document["_id"]
        data['type_'] = 'pdf'
        data['timestamp'] = str(datetime.now())
        data['_id'] = _id
        data['user_id'] = user_id
        chats_collection.insert_one(data)
        content_collection.update_one(
            {"_id": document["_id"]},
            {"$push": {"chat_ids": _id}})
        return jsonify({"msg": "Chat created successfully", 'chat': data}), 201

# create a sammary from pdf
@app.route("/sammary/<string:pdf_id>", methods=["POST"])
def create_sammary1(pdf_id):
    res= authorise_request(request)
    if(res=="expired"):
        return jsonify({"message": "Token expired"}), 403
    elif (res=="invalid"):
        return jsonify({"message": "Token is invalid"}),403
    elif(res=="not found"):
        return jsonify({"message": "Token not found"}),403
    elif(res=="revoked"):
        return jsonify({"message": "Token is revoked"}),403
    else:
        user_id=res["id"]
        document = content_collection.find_one({"_id": pdf_id})
        context = document['extracted_text']
        question = "Create me a summary"
        _id = str(ObjectId())
        response = openai.Completion.create(
            engine="text-davinci-002",
            prompt=f"Context: {context}\nQuestion: {question}\nAnswer:",
            max_tokens=50
        )
        _id = str(ObjectId())
        
        
        answer = response.choices[0].text.strip()
        answer1 = f'{context[:25]}...'
        time = str(datetime.now())
        data = {
            'sammary': answer,
            "type": "pdf",
            "prompt":context,
            "pdf_id": str(document["_id"]),
            "title": answer1,
            'timestamp': time,
            '_id': _id,
            'user_id': user_id
        }
        sammary = sammaries_collection.insert_one(data)
        response_data = {
            "msg": "Chat created successfully",
            "sammary": answer
        }
        return jsonify(response_data), 201

# saving sammaries 
@app.route("/sammary/save", methods=["POST"])
def save_sammary1():
    res= authorise_request(request)
    if(res=="expired"):
        return jsonify({"message": "Token expired"}), 403
    elif (res=="invalid"):
        return jsonify({"message": "Token is invalid"}),403
    elif(res=="not found"):
        return jsonify({"message": "Token not found"}),403
    elif(res=="revoked"):
        return jsonify({"message": "Token is revoked"}),403
    else:
        data = request.get_json()
        sammary=data["sammary"]
        type=data["type"]
        pdf_id=data["pdf_id"]
        prompt=data["prompt"]
        time = str(datetime.now())
        timestamp= time
        title= data["title"]
        _id = str(ObjectId())
        user_id= res["id"]
        data = {
            "title": title,
            'sammary': sammary,
            "type_": type,
            "pdf_id": pdf_id,
            'timestamp': timestamp,
            '_id': _id,
            'user_id': user_id,
            "prompt":prompt
        }
        sammary = sammaries_collection.insert_one(data)
        response_data = {
            "msg": "sammary created successfully"
        }
        return jsonify(response_data), 201

# create sammaries from text data
@app.route("/sammary", methods=["POST"])
def create_sammary():
    res= authorise_request(request)
    if(res=="expired"):
        return jsonify({"message": "Token expired"}), 403
    elif (res=="invalid"):
        return jsonify({"message": "Token is invalid"}),403
    elif(res=="not found"):
        return jsonify({"message": "Token not found"}),403
    elif(res=="revoked"):
        return jsonify({"message": "Token is revoked"}),403
    else:
        user_id=res["id"]
        data = request.get_json()
        text = data["text"]
        context = text
        question = "Create me a summary"
        _id = str(ObjectId())
        response = openai.Completion.create(
            engine="text-davinci-002",
            prompt=f"Context: {context}\nQuestion: {question}\nAnswer:",
            max_tokens=50
        )
        answer = response.choices[0].text.strip()
        answer1 = f'{context[:25]}...'
        time = str(datetime.now())
        data = {
            'sammary': answer,
            "pdf_id": "",
            "title": answer1,
            "type_": "text",
            "prompt":text,
            'timestamp': time,
            '_id': _id,
            'user_id': user_id,
    
        }
       
            
        # sammary = sammaries_collection.insert_one(data)
        response_data = {
            "msg": "Summary created successfully",
            "sammary": answer,"prompt":text
        }
        return jsonify(response_data), 201

# get all chats
@app.route("/chats", methods=["GET"])
def get_all_chats():
    res= authorise_request(request)
    if(res=="expired"):
        return jsonify({"message": "Token expired"}), 403
    elif (res=="invalid"):
        return jsonify({"message": "Token is invalid"}),403
    elif(res=="not found"):
        return jsonify({"message": "Token not found"}),403
    elif(res=="revoked"):
        return jsonify({"message": "Token is revoked"}),403
    else:
        chats = chats_collection.find({"user_id":res["id"]})
        chat_list = [chat for chat in chats]
        return jsonify(chat_list), 200

# getting all sammaries
@app.route("/sammary", methods=["GET"])
def get_summaries():
    res= authorise_request(request)
    if(res=="expired"):
        return jsonify({"message": "Token expired"}), 403
    elif (res=="invalid"):
        return jsonify({"message": "Token is invalid"}),403
    elif(res=="not found"):
        return jsonify({"message": "Token not found"}),403
    elif(res=="revoked"):
        return jsonify({"message": "Token is revoked"}),403
    else:
        print(res)
        sammaries = list(sammaries_collection.find({"user_id":res["id"]}))
        # sammary_list = []
        # for sammary in sammaries:
        #     formatted_sammary = {
        #         "type": sammary["type"],
        #         "sammary_id": str(sammary["_id"]),
        #         "sammary": sammary["sammary"],
        #         "pdf_id": sammary["pdf_id"],
        #         "timestamp": sammary["timestamp"],
        #         "user_id": sammary["user_id"]
        #     }
        #     sammary_list.append(formatted_sammary)
        response_data = {
            "summaries": sammaries
        }
        return jsonify(response_data), 200
from flask import request

# delete one sammary
@app.route("/sammary/<summary_id>", methods=["DELETE"])
def delete_summary(sammary_id):
    res = authorise_request(request)
    if res == "expired":
        return jsonify({"message": "Token expired"}), 403
    elif res == "invalid":
        return jsonify({"message": "Token is invalid"}), 403
    elif res == "not found":
        return jsonify({"message": "Token not found"}), 403
    elif res == "revoked":
        return jsonify({"message": "Token is revoked"}), 403
    else:
        # Add code here to delete a specific summary by summary_id
        # You can use 
        sammaries_collection.delete_one({"_id": sammary_id})
        # Return an appropriate response based on the success or failure of the deletion
        return jsonify({"message": "Sammary deleted successfully"}), 200

@app.route("/sammaries/pdfs/<string:pdf_id>", methods=["GET"])
def get_summaries_by_pdf_id(pdf_id):
    res= authorise_request(request)
    if(res=="expired"):
        return jsonify({"message": "Token expired"}), 403
    elif (res=="invalid"):
        return jsonify({"message": "Token is invalid"}),403
    elif(res=="not found"):
        return jsonify({"message": "Token not found"}),403
    elif(res=="revoked"):
        return jsonify({"message": "Token is revoked"}),403
    else:
        chats = list(sammaries_collection.find({"pdf_id": pdf_id}))
        return jsonify(chats), 200

# getting all chats
@app.route("/chats", methods=["GET"])
def get_chats():
    res= authorise_request(request)
    if(res=="expired"):
        return jsonify({"message": "Token expired"}), 403
    elif (res=="invalid"):
        return jsonify({"message": "Token is invalid"}),403
    elif(res=="not found"):
        return jsonify({"message": "Token not found"}),403
    elif(res=="revoked"):
        return jsonify({"message": "Token is revoked"}),403
    else:
        user_id =res["id"]
        chats = list(chats_collection.find({'user_id': user_id}))
        return jsonify(chats), 200

# getting all chats under pdf
@app.route("/chats/pdfs/<string:pdf_id>", methods=["GET"])
def get_chats_by_pdf_id(pdf_id):
    res= authorise_request(request)
    if(res=="expired"):
        return jsonify({"message": "Token expired"}), 403
    elif (res=="invalid"):
        return jsonify({"message": "Token is invalid"}),403
    elif(res=="not found"):
        return jsonify({"message": "Token not found"}),403
    elif(res=="revoked"):
        return jsonify({"message": "Token is revoked"}),403
    else:
        chats = list(chats_collection.find({"pdf_id": pdf_id}))
        return jsonify(chats), 200

# getting specific chat
@app.route("/chats/<string:chat_id>", methods=["GET"])
def get_chat(chat_id):
    res= authorise_request(request)
    if(res=="expired"):
        return jsonify({"message": "Token expired"}), 403
    elif (res=="invalid"):
        return jsonify({"message": "Token is invalid"}),403
    elif(res=="not found"):
        return jsonify({"message": "Token not found"}),403
    elif(res=="revoked"):
        return jsonify({"message": "Token is revoked"}),403
    else:
        _id=res["id"]
        chat = chats_collection.find_one({"_id": chat_id, 'user_id': _id})
        if chat:
            chat["_id"] = str(chat["_id"])
            return jsonify({"chat": chat}), 200
        else:
            return jsonify({"msg": "Chat not found"}), 404

@app.route("/chats/<string:chat_id>", methods=["PUT"])
def update_chat(chat_id):
    res= authorise_request(request)
    if(res=="expired"):
        return jsonify({"message": "Token expired"}), 403
    elif (res=="invalid"):
        return jsonify({"message": "Token is invalid"}),403
    elif(res=="not found"):
        return jsonify({"message": "Token not found"}),403
    elif(res=="revoked"):
        return jsonify({"message": "Token is revoked"}),403
    else:
        _id = res["id"]
        data = request.get_json()
        result = chats_collection.update_one({"_id": chat_id, 'user_id': _id}, {"$set": data})
        if result.modified_count == 1:
            return jsonify({"msg": "Chat updated successfully"}), 200
        else:
            return jsonify({"msg": "Chat not found"}), 404
# delete chat
@app.route("/chats/<string:chat_id>", methods=["DELETE"])
def delete_chat(chat_id):
    res= authorise_request(request)
    if(res=="expired"):
        return jsonify({"message": "Token expired"}), 403
    elif (res=="invalid"):
        return jsonify({"message": "Token is invalid"}),403
    elif(res=="not found"):
        return jsonify({"message": "Token not found"}),403
    elif(res=="revoked"):
        return jsonify({"message": "Token is revoked"}),403
    else:
        _id = res["id"]
        result = chats_collection.delete_one({"_id": chat_id, 'user_id': _id})
        if result.deleted_count == 1:
            return jsonify({"msg": "Chat deleted successfully"}), 200
        else:
            return jsonify({"msg": "Chat not found"}), 404

def extract_text_from_pdf(pdf_file_path):
    try:
        text = ''
        with open(pdf_file_path, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            pages = pdf_reader.pages
            for page_number in range(len(pages)):
                page = pdf_reader.pages[page_number]
                text += page.extract_text()
            return text
    except Exception as e:
        return text
def get_token(id):
    paylod={
     "id": id,
    }
    token = jwt.encode(paylod, secret_key, algorithm=algorithm)
    return token

def extract_text_from_image(image_path):
    try:
        image = Image.open(image_path)
        extracted_text = pytesseract.image_to_string(image)
        return extracted_text
    except Exception as e:
        return f"Error: {str(e)}"

def authorise_request(request1):
    token = request1.headers.get('Authorization')
    if token:
        if(token in revoked_tokens):
            return 'revoked'
        # You can perform additional checks on the header here if needed
        try:
            decoded_payload = jwt.decode(token, secret_key, algorithms=[algorithm])
            return decoded_payload
        except jwt.ExpiredSignatureError:
            return "expired"
        except jwt.InvalidTokenError:
            return "invalid"
    else:
        return "not found"
def revoke_token(token):
    revoked_tokens1=revoked_tokens
    revoked_tokens.append(token)
    if len(revoked_tokens1)<len(revoked_tokens):
        print()
        return "revoked"
if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=8085)
