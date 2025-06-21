from flask import flask

app = flask(__name__)

app.route('/')
def home():
    return 'hola mundo flask'

if __name__ == '__main__':
    app.run(port=4000, debug=True)