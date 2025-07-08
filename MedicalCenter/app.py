from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from functools import wraps
from datetime import datetime
from flask_wtf.csrf import CSRFProtect


app = Flask(__name__)
app.secret_key = 'medical12345'

csrf = CSRFProtect(app)

# Configuración de la base de datos
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'medicalcenter'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

# Decorador para verificar sesión
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'loggedin' not in session:
            flash('Debe iniciar sesión primero', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# Decorador para verificar privilegios
def privilege_required(privilegio):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'privilegio' not in session or session['privilegio'] < privilegio:
                flash('No tiene permisos para acceder a esta sección', 'warning')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        rfc = request.form['rfc']
        contrasena = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Buscar usuario por RFC
            cursor.execute("SELECT * FROM usuarios WHERE rfc = %s", (rfc,))
            usuario = cursor.fetchone()
            
            if usuario:
                # Verificar contraseña (SHA-256)
                cursor.execute("SELECT SHA2(%s, 256) AS hash", (contrasena,))
                hashed_password = cursor.fetchone()['hash']
                
                if usuario['contrasena'] == hashed_password:
                    session['loggedin'] = True
                    session['id_usuario'] = usuario['id_usuario']
                    session['rfc'] = usuario['rfc']
                    session['privilegio'] = usuario['privilegio']
                    flash('Inicio de sesión exitoso', 'success')
                    return redirect(url_for('dashboard'))
            
            flash('RFC o contraseña incorrectos', 'danger')
        
        except Exception as e:
            flash(f'Error en el sistema: {str(e)}', 'danger')
        
        finally:
            cursor.close()
            conn.close()
    
    return render_template('index.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión', 'success')
    return redirect(url_for('home'))

@app.template_filter('formato_fecha_input')
def formato_fecha_input(value):
    """Convierte fecha a formato YYYY-MM-DD para campos input type=date"""
    if not value:
        return ''
    return value.strftime('%Y-%m-%d')


@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/pacientes', methods=['GET', 'POST'])
@login_required
def pacientes():
    try:
        conn = get_db_connection()
        if conn is None:
            flash('Error de conexión con la base de datos', 'danger')
            return render_template('pacientes.html', pacientes=[])

        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            action = request.form.get('action')

            if action == 'create':
                nombres = request.form['nombres']
                apellidos = request.form['apellidos']
                fecha_nacimiento = request.form['fecha_nacimiento']
                genero = request.form['genero']
                tipo_sangre = request.form['tipo_sangre']
                alergias = request.form['alergias']

                try:
                    datetime.strptime(fecha_nacimiento, '%Y-%m-%d')
                except ValueError:
                    flash('Formato de fecha inválido. Use AAAA-MM-DD', 'danger')
                    return redirect(url_for('pacientes'))

                cursor.execute(
                    "INSERT INTO pacientes (nombres, apellidos, fecha_nacimiento, genero, tipo_sangre, alergias, estatus) "
                    "VALUES (%s, %s, %s, %s, %s, %s, 1)",
                    (nombres, apellidos, fecha_nacimiento, genero, tipo_sangre, alergias)
                )
                conn.commit()
                flash('Paciente creado exitosamente', 'success')
                return redirect(url_for('pacientes'))

            elif action == 'update':
                id_paciente = request.form['id_paciente']
                nombres = request.form['nombres']
                apellidos = request.form['apellidos']
                fecha_nacimiento = request.form['fecha_nacimiento']
                genero = request.form['genero']
                tipo_sangre = request.form['tipo_sangre']
                alergias = request.form['alergias']

                cursor.execute(
                    "UPDATE pacientes SET nombres = %s, apellidos = %s, fecha_nacimiento = %s, "
                    "genero = %s, tipo_sangre = %s, alergias = %s WHERE id_paciente = %s",
                    (nombres, apellidos, fecha_nacimiento, genero, tipo_sangre, alergias, id_paciente)
                )
                conn.commit()
                flash('Paciente actualizado exitosamente', 'success')

            elif action == 'delete':
                id_paciente = request.form['id_paciente']
                cursor.execute(
                    "UPDATE pacientes SET estatus = 0 WHERE id_paciente = %s",
                    (id_paciente,)
                )
                conn.commit()
                flash('Paciente eliminado exitosamente', 'success')

        # Obtener pacientes activos (para GET y después de POST)
        cursor.execute("SELECT * FROM pacientes WHERE estatus = 1")
        pacientes = cursor.fetchall()

        return render_template('pacientes.html', pacientes=pacientes)

    except mysql.connector.Error as err:
        flash(f'Error de base de datos: {err.msg}', 'danger')
        return render_template('pacientes.html', pacientes=[])
    except Exception as e:
        flash(f'Error inesperado: {str(e)}', 'danger')
        return render_template('pacientes.html', pacientes=[])
    finally:
        try:
            if 'cursor' in locals() and cursor:
                cursor.close()
            if 'conn' in locals() and conn and conn.is_connected():
                conn.close()
        except:
            pass

@app.route('/medico/<int:id_medico>')
@login_required
def ver_medico(id_medico):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM medicos WHERE id_medico = %s", (id_medico,))
    medico = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not medico:
        flash('Médico no encontrado', 'danger')
        return redirect(url_for('medicos'))
    
    return render_template('ver_medico.html', medico=medico)

@app.route('/medicos', methods=['GET', 'POST'])
@login_required
@privilege_required(2)
def medicos():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        # CRUD para médicos
        action = request.form.get('action')
        
        if action == 'create':
            primer_nombre = request.form['primer_nombre']
            segundo_nombre = request.form.get('segundo_nombre', '')
            apellido_paterno = request.form['apellido_paterno']
            apellido_materno = request.form.get('apellido_materno', '')
            cedula_profesional = request.form['cedula_profesional']
            especialidad = request.form['especialidad']
            correo = request.form['correo']
            rfc = request.form['rfc']
            telefono = request.form['telefono']
            centro_medico = request.form['centro_medico']
            
            # Crear usuario médico
            cursor.execute(
                "INSERT INTO usuarios (rfc, contrasena, privilegio) "
                "VALUES (%s, SHA2('temp_password', 256), 1)",
                (rfc,)
            )
            user_id = cursor.lastrowid
            
            # Crear médico
            cursor.execute(
                "INSERT INTO medicos (primer_nombre, segundo_nombre, apellido_paterno, apellido_materno, "
                "cedula_profesional, especialidad, correo, rfc, telefono, centro_medico) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (primer_nombre, segundo_nombre, apellido_paterno, apellido_materno, 
                 cedula_profesional, especialidad, correo, rfc, telefono, centro_medico)
            )
            conn.commit()
            flash('Médico registrado exitosamente', 'success')
        
        elif action == 'update':
            id_medico = request.form['id_medico']
            primer_nombre = request.form['primer_nombre']
            segundo_nombre = request.form.get('segundo_nombre', '')
            apellido_paterno = request.form['apellido_paterno']
            apellido_materno = request.form.get('apellido_materno', '')
            cedula_profesional = request.form['cedula_profesional']
            especialidad = request.form['especialidad']
            correo = request.form['correo']
            rfc = request.form['rfc']  # Nuevo campo RFC
            telefono = request.form['telefono']
            centro_medico = request.form['centro_medico']
            
            cursor.execute(
                "UPDATE medicos SET primer_nombre = %s, segundo_nombre = %s, apellido_paterno = %s, "
                "apellido_materno = %s, cedula_profesional = %s, especialidad = %s, correo = %s, "
                "telefono = %s, centro_medico = %s, rfc = %s WHERE id_medico = %s",
                (primer_nombre, segundo_nombre, apellido_paterno, apellido_materno, 
                 cedula_profesional, especialidad, correo, telefono, centro_medico, rfc, id_medico)
            )
            conn.commit()
            flash('Médico actualizado exitosamente', 'success')
        
        elif action == 'delete':
            id_medico = request.form['id_medico']
            rfc = request.form['rfc']
            
            # Soft delete del médico
            cursor.execute(
                "UPDATE medicos SET estatus = 0 WHERE id_medico = %s",
                (id_medico,)
            )
            
            # Soft delete del usuario médico
            cursor.execute(
                "UPDATE usuarios SET estatus = 0 WHERE rfc = %s",
                (rfc,)
            )
            conn.commit()
            flash('Médico eliminado exitosamente', 'success')
    
    # Obtener médicos activos
    cursor.execute("SELECT * FROM medicos WHERE estatus = 1")
    medicos = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('medicos.html', medicos=medicos)


@app.route('/pacientes/<int:id_paciente>')
@login_required
def ver_paciente(id_paciente):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM pacientes WHERE id_paciente = %s", (id_paciente,))
    paciente = cursor.fetchone()

    cursor.close()
    conn.close()

    if not paciente:
        flash("Paciente no encontrado.", "danger")
        return redirect(url_for('pacientes'))

    return render_template("ver_paciente.html", paciente=paciente)


# Funciones para Jinja2
@app.template_filter('format_fecha')
def format_fecha(value):
    if value is None:
        return ""
    return value.strftime('%d/%m/%Y')


def calcular_edad(fecha_nacimiento):
    if not fecha_nacimiento:
        return "N/A"
    
    hoy = datetime.now().date()
    edad = hoy.year - fecha_nacimiento.year - (
        (hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))
    return edad

app.jinja_env.filters['format_fecha'] = format_fecha
app.jinja_env.filters['calcular_edad'] = calcular_edad

if __name__ == '__main__':
    app.run(port=4000, debug=True)