from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/medicos')
def medicos():
    return render_template('medicos.html')

@app.route('/pacientes')
def pacientes():
    return render_template('pacientes.html')

if __name__ == '__main__':
    app.run(port=4000, debug=True)