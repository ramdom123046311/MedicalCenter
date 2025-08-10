
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import mysql.connector
from functools import wraps
from datetime import datetime
from flask_wtf.csrf import CSRFProtect
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import io

app = Flask(__name__)
app.secret_key = 'medical12345'

# Configuración CSRF
csrf = CSRFProtect(app)
app.config['WTF_CSRF_TIME_LIMIT'] = 3600 

# Configuración de la base de datos
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '2983',
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

#verificar privilegios
def privilege_required(privilegio):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'privilegio' not in session or session['privilegio'] < privilegio:
                flash('No tiene permisos para acceder a esta sección', 'warning')
                return redirect(url_for('citas'))
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
                # Verificar contraseña
                cursor.execute("SELECT SHA2(%s, 256) AS hash", (contrasena,))
                hashed_password = cursor.fetchone()['hash']
                
                if usuario['contrasena'] == hashed_password:
                    session['loggedin'] = True
                    session['id_usuario'] = usuario['id_usuario']
                    session['rfc'] = usuario['rfc']
                    session['privilegio'] = usuario['privilegio']
                    flash('Inicio de sesión exitoso', 'success')
                    return redirect(url_for('citas'))
            
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

# ===== RUTA: Listado de expedientes =====
@app.route('/expedientes')
def expedientes():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT e.id, 
                   CONCAT(p.nombres, ' ', p.apellidos) AS paciente_nombre,
                   e.diagnostico, 
                   e.fecha AS fecha_creacion
            FROM expedientes e
            JOIN pacientes p ON e.paciente_id = p.id_paciente
            WHERE e.deleted = 0
            ORDER BY e.fecha DESC
        """)
        expedientes = cursor.fetchall()
        
        return render_template('expedientes.html', expedientes=expedientes)
        
    except mysql.connector.Error as err:
        flash(f'Error de base de datos: {err}', 'danger')
        return render_template('expedientes.html', expedientes=[])
        
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/expedientes/crear/<int:paciente_id>')
def crear_expediente(paciente_id):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # CORRECCIÓN: Cambiar ORDER BY id -> ORDER BY id_exploradon
        cursor.execute("""
            SELECT id_paciente, diagnostico
            FROM exploracion
            WHERE id_paciente = %s
            ORDER BY id_exploracion DESC  
            LIMIT 1
        """, (paciente_id,))
        exploracion = cursor.fetchone()

        if not exploracion:
            flash("No hay datos de exploración para este paciente", "warning")
            return redirect(url_for("citas"))

        cursor.execute("""
            INSERT INTO expedientes (paciente_id, diagnostico)
            VALUES (%s, %s)
        """, (exploracion["id_paciente"], exploracion["diagnostico"]))
        conn.commit()

        flash("Expediente creado exitosamente", "success")
        return redirect(url_for("expedientes"))

    except mysql.connector.Error as err:
        flash(f"Error en la base de datos: {err}", "danger")
        return redirect(url_for("citas"))
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

@app.template_filter('formato_fecha_input')
def formato_fecha_input(value):
    """Convierte fecha a formato YYYY-MM-DD para campos input type=date"""
    if not value:
        return ''
    return value.strftime('%Y-%m-%d')


# Ruta citas - Modificada para manejar errores y datos del formulario
@app.route('/citas')
@login_required
def citas():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Consulta modificada: Añade C.id_paciente y C.id_medico
    cursor.execute("""
        SELECT C.id_cita, C.id_paciente, C.id_medico,
               CONCAT(P.nombres, ' ', P.apellidos) AS nombre_paciente,
               CONCAT(M.primer_nombre, ' ', M.apellido_paterno) AS nombre_medico,
               C.fecha, C.hora, C.motivo, C.estatus
        FROM Cita C
        JOIN Pacientes P ON C.id_paciente = P.id_paciente
        JOIN Medicos M ON C.id_medico = M.id_medico
        WHERE C.estado = 1
    """)
    citas = cursor.fetchall()

    cursor.execute("""
        SELECT id_paciente, CONCAT(nombres, ' ', apellidos) AS nombre_completo 
        FROM Pacientes 
        WHERE estatus = 1
    """)
    pacientes = cursor.fetchall()

    cursor.execute("""
        SELECT id_medico, CONCAT(primer_nombre, ' ', apellido_paterno) AS nombre_completo 
        FROM Medicos 
        WHERE estatus = 1
    """)
    medicos = cursor.fetchall()

    cursor.close()
    conn.close()

    # Recuperar datos del formulario si existe en la sesión
    form_data = session.pop('form_data', None) or {}
    modo_edicion = 'id_cita' in form_data
    
    # Recuperar errores si existen
    errors = session.pop('errors', None) or {}
    
    return render_template(
        'citas.html',
        citas=citas,
        pacientes=pacientes,
        medicos=medicos,
        form_data=form_data,
        modo_edicion=modo_edicion,
        errors=errors
    )
    # Obtener datos del formulario de la sesión si existen
    
# Agregar cita - Modificada para manejar errores y datos del formulario
@app.route('/agregar_cita', methods=['POST'])
def agregar_cita():
    form_data = {
        'id_paciente': request.form['id_paciente'],
        'id_medico': request.form['id_medico'],
        'fecha': request.form['fecha'],
        'hora': request.form['hora'],
        'motivo': request.form['motivo'].strip()
    }
    
    errors = {}

    if not form_data['id_paciente']:
        errors['id_paciente'] = "Seleccione un paciente"
    if not form_data['id_medico']:
        errors['id_medico'] = "Seleccione un médico"
    if not form_data['fecha']:
        errors['fecha'] = "La fecha es obligatoria"
    if not form_data['hora']:
        errors['hora'] = "La hora es obligatoria"
    if not form_data['motivo']:
        errors['motivo'] = "El motivo es obligatorio"
    elif len(form_data['motivo']) < 3:
        errors['motivo'] = "El motivo debe tener al menos 3 caracteres"
    
    try:
        fecha_obj = datetime.strptime(form_data['fecha'], '%Y-%m-%d')
        if fecha_obj < datetime.today():
            errors['fecha'] = "La fecha no puede ser anterior a hoy"
    except ValueError:
        errors['fecha'] = "Fecha inválida"

    if errors:
        # Guardar errores y datos del formulario en la sesión
        session['errors'] = errors
        session['form_data'] = form_data
        return redirect(url_for('citas'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO Cita (id_paciente, id_medico, fecha, hora, motivo)
        VALUES (%s, %s, %s, %s, %s)
    """, (form_data['id_paciente'], form_data['id_medico'], form_data['fecha'], form_data['hora'], form_data['motivo']))
    conn.commit()
    cursor.close()
    conn.close()
    
    # Limpiar datos de sesión después de éxito
    if 'errors' in session:
        session.pop('errors')
    if 'form_data' in session:
        session.pop('form_data')
        
    flash('Cita agendada correctamente', 'success')
    return redirect(url_for('citas'))

# Ruta para cargar formulario de edición
@app.route('/editar_cita/<int:id_cita>')
def editar_cita(id_cita):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Obtener datos de la cita específica
    cursor.execute("""
        SELECT C.id_cita, C.id_paciente, C.id_medico, C.fecha, C.hora, C.motivo
        FROM Cita C
        WHERE C.id_cita = %s
    """, (id_cita,))
    cita = cursor.fetchone()
    
    # Obtener listas de pacientes y médicos activos
    cursor.execute("""
        SELECT id_paciente, CONCAT(nombres, ' ', apellidos) AS nombre_completo 
        FROM Pacientes 
        WHERE estatus = 1
    """)
    pacientes = cursor.fetchall()

    cursor.execute("""
        SELECT id_medico, CONCAT(primer_nombre, ' ', apellido_paterno) AS nombre_completo 
        FROM Medicos 
        WHERE estatus = 1
    """)
    medicos = cursor.fetchall()

    cursor.close()
    conn.close()
    
    if not cita:
        flash('Cita no encontrada', 'danger')
        return redirect(url_for('citas'))
    
    # Preparar datos para el formulario
    form_data = {
        'id_cita': cita['id_cita'],
        'id_paciente': cita['id_paciente'],
        'id_medico': cita['id_medico'],
        'fecha': cita['fecha'].strftime('%Y-%m-%d') if cita['fecha'] else '',
        'hora': str(cita['hora']) if cita['hora'] else '',
        'motivo': cita['motivo']
    }
    
    return render_template('citas.html', 
                          citas=session.get('citas', []), 
                          pacientes=pacientes, 
                          medicos=medicos, 
                          form_data=form_data,
                          modo_edicion=True)

# Ruta para actualizar cita
@app.route('/actualizar_cita/<int:id_cita>', methods=['POST'])
def actualizar_cita(id_cita):
    form_data = {
        'id_paciente': request.form['id_paciente'],
        'id_medico': request.form['id_medico'],
        'fecha': request.form['fecha'],
        'hora': request.form['hora'],
        'motivo': request.form['motivo'].strip()
    }
    
    errors = {}
    
    # Validaciones (igual que en agregar_cita)
    if not form_data['id_paciente']:
        errors['id_paciente'] = "Seleccione un paciente"
    if not form_data['id_medico']:
        errors['id_medico'] = "Seleccione un médico"
    if not form_data['fecha']:
        errors['fecha'] = "La fecha es obligatoria"
    if not form_data['hora']:
        errors['hora'] = "La hora es obligatoria"
    if not form_data['motivo']:
        errors['motivo'] = "El motivo es obligatorio"
    elif len(form_data['motivo']) < 3:
        errors['motivo'] = "El motivo debe tener al menos 3 caracteres"
    
    try:
        fecha_obj = datetime.strptime(form_data['fecha'], '%Y-%m-%d')
        if fecha_obj < datetime.today():
            errors['fecha'] = "La fecha no puede ser anterior a hoy"
    except ValueError:
        errors['fecha'] = "Fecha inválida"

    if errors:
        session['errors'] = errors
        session['form_data'] = form_data
        return redirect(url_for('editar_cita', id_cita=id_cita))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE Cita 
        SET id_paciente = %s, id_medico = %s, fecha = %s, hora = %s, motivo = %s
        WHERE id_cita = %s
    """, (form_data['id_paciente'], form_data['id_medico'], form_data['fecha'], 
          form_data['hora'], form_data['motivo'], id_cita))
    conn.commit()
    cursor.close()
    conn.close()
    
    # Limpiar datos de sesión después de éxito
    if 'errors' in session:
        session.pop('errors')
    if 'form_data' in session:
        session.pop('form_data')
        
    flash('Cita actualizada correctamente', 'success')
    return redirect(url_for('citas'))

# Cancelar cita
@app.route('/cancelar_cita/<int:id_cita>', methods=['POST'])
def cancelar_cita(id_cita):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Cita SET estatus = 'cancelada' WHERE id_cita = %s", (id_cita,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Cita cancelada correctamente', 'warning')
    return redirect(url_for('citas'))

# Eliminar cita (soft delete)
@app.route('/eliminar_cita/<int:id_cita>', methods=['POST'])
def eliminar_cita(id_cita):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Cita SET estado = 0 WHERE id_cita = %s", (id_cita,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Cita eliminada correctamente', 'danger')
    return redirect(url_for('citas'))
#AQUI ESTAN LAS CITAS....................

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
                errores = {}

                nombres  = request.form.get('nombres', '').strip()
                apellidos = request.form.get('apellidos', '').strip()
                fecha_nacimiento = request.form.get('fecha_nacimiento', '').strip()
                genero   = request.form.get('genero', '').strip()
                tipo_sangre = request.form.get('tipo_sangre', '').strip()
                alergias = request.form.get('alergias', '').strip()

                # Validaciones
                if not nombres:
                    errores['nombres'] = 'El nombre es obligatorio'
                if not apellidos:
                    errores['apellidos'] = 'Los apellidos son obligatorios'
                try:
                    datetime.strptime(fecha_nacimiento, '%Y-%m-%d')
                except ValueError:
                    errores['fecha_nacimiento'] = 'Fecha inválida (AAAA‑MM‑DD)'
                if genero not in ['Masculino', 'Femenino', 'Otro']:
                    errores['genero'] = 'Seleccione un género válido'
                if tipo_sangre not in ['Desconocido','A+','A-','B+','B-','AB+','AB-','O+','O-']:
                    errores['tipo_sangre'] = 'Tipo de sangre inválido'

                if errores:
                    cursor.execute("SELECT * FROM pacientes WHERE estatus = 1")
                    pacientes = cursor.fetchall()
                    return render_template(
                        'pacientes.html',
                        pacientes=pacientes,
                        errores=errores,
                        form_data=request.form
                    )

                cursor.execute(
                    """INSERT INTO pacientes
                       (nombres, apellidos, fecha_nacimiento, genero,
                        tipo_sangre, alergias, estatus)
                       VALUES (%s, %s, %s, %s, %s, %s, 1)""",
                    (nombres, apellidos, fecha_nacimiento,
                     genero, tipo_sangre, alergias)
                )
                conn.commit()
                flash('Paciente creado exitosamente', 'success')
                return redirect(url_for('pacientes'))

            elif action == 'update':
                id_paciente = request.form['id_paciente']
                nombres  = request.form.get('nombres', '').strip()
                apellidos = request.form.get('apellidos', '').strip()
                fecha_nacimiento = request.form.get('fecha_nacimiento', '').strip()
                genero   = request.form.get('genero', '').strip()
                tipo_sangre = request.form.get('tipo_sangre', '').strip()
                alergias = request.form.get('alergias', '').strip()

                errores = {}
                if not nombres:
                    errores['nombres'] = 'El nombre es obligatorio'
                if not apellidos:
                    errores['apellidos'] = 'Los apellidos son obligatorios'
                try:
                    datetime.strptime(fecha_nacimiento, '%Y-%m-%d')
                except ValueError:
                    errores['fecha_nacimiento'] = 'Fecha inválida (AAAA‑MM‑DD)'

                if genero not in ['Masculino', 'Femenino', 'Otro']:
                    errores['genero'] = 'Seleccione un género válido'
                if tipo_sangre not in ['Desconocido','A+','A-','B+','B-','AB+','AB-','O+','O-']:
                    errores['tipo_sangre'] = 'Tipo de sangre inválido'

                if errores:
                    cursor.execute("SELECT * FROM pacientes WHERE estatus = 1")
                    pacientes = cursor.fetchall()
                    return render_template(
                        'pacientes.html',
                        pacientes=pacientes,
                        errores=errores,
                        form_data=request.form
                    )

                cursor.execute(
                    """UPDATE pacientes
                       SET nombres=%s, apellidos=%s, fecha_nacimiento=%s,
                           genero=%s, tipo_sangre=%s, alergias=%s
                       WHERE id_paciente=%s""",
                    (nombres, apellidos, fecha_nacimiento,
                     genero, tipo_sangre, alergias, id_paciente)
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
        action = request.form.get('action')

       
        if action == 'create':
            errores = {}

            primer_nombre = request.form.get('primer_nombre', '').strip()
            segundo_nombre = request.form.get('segundo_nombre', '').strip()
            apellido_paterno = request.form.get('apellido_paterno', '').strip()
            apellido_materno = request.form.get('apellido_materno', '').strip()
            cedula_profesional = request.form.get('cedula_profesional', '').strip()
            especialidad = request.form.get('especialidad', '').strip()
            correo = request.form.get('correo', '').strip()
            rfc = request.form.get('rfc', '').strip()
            telefono = request.form.get('telefono', '').strip()
            centro_medico = request.form.get('centro_medico', '').strip()
            contrasena = request.form.get('contrasena', '').strip()
            confirmar_contrasena = request.form.get('confirmar_contrasena', '').strip()
            
            if not primer_nombre:
                errores['primer_nombre'] = 'Nombre obligatorio'
            if not apellido_paterno:
                errores['apellido_paterno'] = 'Apellido paterno obligatorio'
            if not apellido_materno:
                errores['apellido_materno'] = 'Apellido materno obligatorio'
            if not cedula_profesional:
                errores['cedula_profesional'] = 'Cédula profesional obligatoria'
            if not correo or '@' not in correo:
                errores['correo'] = 'Correo electrónico inválido'
            if not rfc:
                errores['rfc'] = 'RFC obligatorio'
            if not telefono:
                errores['telefono'] = 'Telefono Obligatorio'
                
            if not contrasena:
                errores['contrasena'] = 'La contraseña es obligatoria'
            elif len(contrasena) < 8:
                errores['contrasena'] = 'La contraseña debe tener al menos 8 caracteres'
    
            if contrasena != confirmar_contrasena:
                errores['confirmar_contrasena'] = 'Las contraseñas no coinciden'

            if errores:
                
                cursor.execute("SELECT * FROM medicos WHERE estatus = 1")
                medicos = cursor.fetchall()
                return render_template(
                    'medicos.html',
                    medicos=medicos,
                    errores_med=errores,    
                    form_data_med=request.form
                )

            cursor.execute(
                "INSERT INTO usuarios (rfc, contrasena, privilegio) "
                "VALUES (%s, SHA2('temp_password', 256), 1)",
                (rfc,)
            )
            cursor.execute(
                """INSERT INTO medicos
                   (primer_nombre, segundo_nombre, apellido_paterno, apellido_materno,
                    cedula_profesional, especialidad, correo, rfc, telefono, centro_medico,contrasena)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (primer_nombre, segundo_nombre, apellido_paterno, apellido_materno,
                 cedula_profesional, especialidad, correo, rfc, telefono, centro_medico,contrasena)
            )
            conn.commit()
            flash('Médico registrado exitosamente', 'success')

        
        elif action == 'update':
            errores = {}
            id_medico  = request.form['id_medico']
            primer_nombre = request.form.get('primer_nombre', '').strip()
            segundo_nombre = request.form.get('segundo_nombre', '').strip()
            apellido_paterno = request.form.get('apellido_paterno', '').strip()
            apellido_materno = request.form.get('apellido_materno', '').strip()
            cedula_profesional = request.form.get('cedula_profesional', '').strip()
            especialidad = request.form.get('especialidad', '').strip()
            correo = request.form.get('correo', '').strip()
            rfc = request.form.get('rfc', '').strip()
            telefono = request.form.get('telefono', '').strip()
            centro_medico = request.form.get('centro_medico', '').strip()

            if not primer_nombre:
                errores['primer_nombre'] = 'Nombre obligatorio'
            if not apellido_paterno:
                errores['apellido_paterno'] = 'Apellido paterno obligatorio'
            if not cedula_profesional:
                errores['cedula_profesional'] = 'Cédula profesional obligatoria'
            if not correo or '@' not in correo:
                errores['correo'] = 'Correo electrónico inválido'

            if errores:
                cursor.execute("SELECT * FROM medicos WHERE estatus = 1")
                medicos = cursor.fetchall()
                return render_template(
                    'medicos.html',
                    medicos=medicos,
                    errores_med=errores,
                    form_data_med=request.form,
                    open_edit=id_medico        
                )

            cursor.execute(
                """UPDATE medicos SET primer_nombre=%s, segundo_nombre=%s, apellido_paterno=%s,
                   apellido_materno=%s, cedula_profesional=%s, especialidad=%s, correo=%s,
                   telefono=%s, centro_medico=%s, rfc=%s
                   WHERE id_medico=%s""",
                (primer_nombre, segundo_nombre, apellido_paterno, apellido_materno,
                 cedula_profesional, especialidad, correo, telefono, centro_medico, rfc, id_medico)
            )
            conn.commit()
            flash('Médico actualizado exitosamente', 'success')

        
        elif action == 'delete':
            id_medico = request.form['id_medico']
            rfc = request.form['rfc']
            cursor.execute("UPDATE medicos SET estatus = 0 WHERE id_medico=%s", (id_medico,))
            cursor.execute("UPDATE usuarios SET estatus = 0 WHERE rfc=%s", (rfc,))
            conn.commit()
            flash('Médico eliminado exitosamente', 'success')

  
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

# Ruta para mostrar formulario de exploración 
@app.route('/exploracion/<int:id_cita>')
@login_required
def exploracion(id_cita):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Verificar si ya existe exploración para esta cita
    cursor.execute("SELECT * FROM Exploracion WHERE id_cita = %s", (id_cita,))
    exploracion_existente = cursor.fetchone()
    
    if exploracion_existente:
        cursor.close()
        conn.close()
        # Redirigir a edición si ya existe
        return redirect(url_for('editar_exploracion', id_exploracion=exploracion_existente['id_exploracion']))
    
    # Obtener datos de la cita y paciente
    cursor.execute("""
        SELECT C.id_cita, C.id_paciente, C.id_medico, 
               P.nombres AS nombres_paciente, P.apellidos AS apellidos_paciente, 
               P.fecha_nacimiento, 
               CONCAT(M.primer_nombre, ' ', M.apellido_paterno) AS nombre_medico
        FROM Cita C
        JOIN Pacientes P ON C.id_paciente = P.id_paciente
        JOIN Medicos M ON C.id_medico = M.id_medico
        WHERE C.id_cita = %s
    """, (id_cita,))
    cita = cursor.fetchone()
    
    if not cita:
        flash('Cita no encontrada', 'danger')
        return redirect(url_for('citas'))
    
    # Calcular edad del paciente
    fecha_nacimiento = cita['fecha_nacimiento']
    hoy = datetime.now().date()
    edad = hoy.year - fecha_nacimiento.year - ((hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))
    
    cursor.close()
    conn.close()
    
    return render_template('exploracion.html', cita=cita, edad=edad, fecha_actual=hoy.strftime('%d/%m/%Y'))

@app.route('/crear_exploracion/<int:id_cita>', methods=['POST'])
@login_required
def crear_exploracion(id_cita):
    datos = {
        'peso': request.form.get('peso'),
        'altura': request.form.get('altura'),
        'temperatura': request.form.get('temperatura'),
        'latidos_minuto': request.form.get('latidos_minuto'),
        'saturacion_oxigeno': request.form.get('saturacion_oxigeno'),
        'glucosa': request.form.get('glucosa'),
        'sintomas': request.form.get('sintomas'),
        'diagnostico': request.form.get('diagnostico'),
        'tratamiento': request.form.get('tratamiento'),
        'estudios': request.form.get('estudios'),
    }

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id_paciente, id_medico FROM Cita WHERE id_cita = %s", (id_cita,))
    cita = cursor.fetchone()

    if not cita:
        flash('Cita no encontrada', 'danger')
        conn.close()
        return redirect(url_for('citas'))

    id_paciente, id_medico = cita

    cursor.execute("""
        INSERT INTO Exploracion (
            id_cita, id_paciente, id_medico, fecha,
            peso, altura, temperatura, latidos_minuto, saturacion_oxigeno, glucosa,
            sintomas, diagnostico, tratamiento, estudios, estatus
        ) VALUES (%s, %s, %s, CURDATE(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
    """, (
        id_cita, id_paciente, id_medico,
        datos['peso'], datos['altura'], datos['temperatura'], datos['latidos_minuto'],
        datos['saturacion_oxigeno'], datos['glucosa'], datos['sintomas'],
        datos['diagnostico'], datos['tratamiento'], datos['estudios']
    ))

    conn.commit()
    id_exploracion = cursor.lastrowid

    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT E.*, 
               CONCAT(P.nombres, ' ', P.apellidos) AS nombre_paciente,
               P.fecha_nacimiento,
               CONCAT(M.primer_nombre, ' ', M.apellido_paterno) AS nombre_medico
        FROM Exploracion E
        JOIN Pacientes P ON E.id_paciente = P.id_paciente
        JOIN Medicos M ON E.id_medico = M.id_medico
        WHERE E.id_exploracion = %s
    """, (id_exploracion,))
    exploracion = cursor.fetchone()
    conn.close()

    fecha_exploracion = exploracion['fecha']
    fecha_nac = exploracion['fecha_nacimiento']
    edad = fecha_exploracion.year - fecha_nac.year - (
        (fecha_exploracion.month, fecha_exploracion.day) < (fecha_nac.month, fecha_nac.day)
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    elements = []
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Center', alignment=1))

    elements.append(Paragraph("<b>MedicalCenter</b>", styles['Center']))
    elements.append(Spacer(1, 24))
    elements.append(Paragraph("Receta Medica", styles['Title']))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"<b>Paciente:</b> {exploracion['nombre_paciente']}", styles['Normal']))
    elements.append(Paragraph(f"<b>Edad:</b> {edad} años", styles['Normal']))
    elements.append(Paragraph(f"<b>Fecha:</b> {exploracion['fecha'].strftime('%d/%m/%Y')}", styles['Normal']))
    elements.append(Paragraph(f"<b>Médico:</b> {exploracion['nombre_medico']}", styles['Normal']))
    elements.append(Spacer(1, 12))

    data = [
        ['Peso (kg)', exploracion['peso'] or 'N/A'],
        ['Altura (cm)', exploracion['altura'] or 'N/A'],
        ['Temperatura (°C)', exploracion['temperatura'] or 'N/A'],
        ['Latidos/min', exploracion['latidos_minuto'] or 'N/A'],
        ['Saturación (%)', exploracion['saturacion_oxigeno'] or 'N/A'],
        ['Glucosa (mg/dL)', exploracion['glucosa'] or 'N/A']
    ]
    table = Table(data, colWidths=[200, 200])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 12))

    elements.append(Paragraph(f"<b>Síntomas:</b> {exploracion['sintomas'] or 'Ninguno'}", styles['Normal']))
    elements.append(Paragraph(f"<b>Diagnóstico:</b> {exploracion['diagnostico'] or 'Ninguno'}", styles['Normal']))
    elements.append(Paragraph(f"<b>Tratamiento:</b> {exploracion['tratamiento'] or 'Ninguno'}", styles['Normal']))
    elements.append(Paragraph(f"<b>Estudios:</b> {exploracion['estudios'] or 'Ninguno'}", styles['Normal']))

    doc.build(elements)
    buffer.seek(0)

    return send_file(buffer, as_attachment=True,
                     download_name=f"reporte_exploracion_{id_exploracion}.pdf",
                     mimetype='application/pdf')
# Ruta para editar exploración
@app.route('/editar_exploracion/<int:id_exploracion>', methods=['GET', 'POST'])
@login_required
def editar_exploracion(id_exploracion):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        # Obtener datos del formulario
        datos = {
            'peso': request.form.get('peso'),
            'altura': request.form.get('altura'),
            'temperatura': request.form.get('temperatura'),
            'latidos_minuto': request.form.get('latidos_minuto'),
            'saturacion_oxigeno': request.form.get('saturacion_oxigeno'),
            'glucosa': request.form.get('glucosa'),
            'sintomas': request.form.get('sintomas'),
            'diagnostico': request.form.get('diagnostico'),
            'tratamiento': request.form.get('tratamiento'),
            'estudios': request.form.get('estudios'),
        }
        
        # Actualizar exploración
        cursor.execute("""
            UPDATE Exploracion SET
                peso = %s, altura = %s, temperatura = %s, 
                latidos_minuto = %s, saturacion_oxigeno = %s, glucosa = %s,
                sintomas = %s, diagnostico = %s, tratamiento = %s, estudios = %s
            WHERE id_exploracion = %s
        """, (
            datos['peso'], datos['altura'], datos['temperatura'], 
            datos['latidos_minuto'], datos['saturacion_oxigeno'], datos['glucosa'],
            datos['sintomas'], datos['diagnostico'], datos['tratamiento'], 
            datos['estudios'], id_exploracion
        ))
        
        conn.commit()
        flash('Exploración actualizada exitosamente', 'success')
        return redirect(url_for('ver_exploracion', id_exploracion=id_exploracion))
    
    # Obtener datos de la exploración
    cursor.execute("""
        SELECT E.*, 
               CONCAT(P.nombres, ' ', P.apellidos) AS nombre_paciente,
               CONCAT(M.primer_nombre, ' ', M.apellido_paterno) AS nombre_medico,
               P.fecha_nacimiento
        FROM Exploracion E
        JOIN Pacientes P ON E.id_paciente = P.id_paciente
        JOIN Medicos M ON E.id_medico = M.id_medico
        WHERE E.id_exploracion = %s
    """, (id_exploracion,))
    exploracion = cursor.fetchone()
    
    if not exploracion:
        flash('Exploración no encontrada', 'danger')
        return redirect(url_for('gestion_exploraciones'))
    
    # Calcular edad del paciente en el momento de la exploración
    fecha_exploracion = exploracion['fecha']
    fecha_nac = exploracion['fecha_nacimiento']
    edad = fecha_exploracion.year - fecha_nac.year - ((fecha_exploracion.month, fecha_exploracion.day) < (fecha_nac.month, fecha_nac.day))
    
    cursor.close()
    conn.close()
    
    return render_template('editar_exploracion.html', exploracion=exploracion, edad=edad)

# Ruta para ver detalles de exploración
@app.route('/ver_exploracion/<int:id_exploracion>')
@login_required
def ver_exploracion(id_exploracion):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT E.*, 
               CONCAT(P.nombres, ' ', P.apellidos) AS nombre_paciente,
               CONCAT(M.primer_nombre, ' ', M.apellido_paterno) AS nombre_medico,
               P.fecha_nacimiento
        FROM Exploracion E
        JOIN Pacientes P ON E.id_paciente = P.id_paciente
        JOIN Medicos M ON E.id_medico = M.id_medico
        WHERE E.id_exploracion = %s
    """, (id_exploracion,))
    exploracion = cursor.fetchone()
    
    if not exploracion:
        flash('Exploración no encontrada', 'danger')
        return redirect(url_for('gestion_exploraciones'))
    
    # Calcular edad del paciente en el momento de la exploración
    fecha_exploracion = exploracion['fecha']
    fecha_nac = exploracion['fecha_nacimiento']
    edad = fecha_exploracion.year - fecha_nac.year - ((fecha_exploracion.month, fecha_exploracion.day) < (fecha_nac.month, fecha_nac.day))
    
    cursor.close()
    conn.close()
    
    return render_template('ver_exploracion.html', exploracion=exploracion, edad=edad)

# Ruta para gestionar exploraciones (listado)
@app.route('/gestion_exploraciones')
@login_required
def gestion_exploraciones():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Obtener todas las exploraciones activas
    cursor.execute("""
        SELECT E.id_exploracion, E.fecha,
               CONCAT(P.nombres, ' ', P.apellidos) AS nombre_paciente,
               CONCAT(M.primer_nombre, ' ', M.apellido_paterno) AS nombre_medico
        FROM Exploracion E
        JOIN Pacientes P ON E.id_paciente = P.id_paciente
        JOIN Medicos M ON E.id_medico = M.id_medico
        WHERE E.estatus = 1
    """)
    exploraciones = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('gestion_exploraciones.html', exploraciones=exploraciones)

# Ruta para eliminar exploración (soft delete)
@app.route('/eliminar_exploracion/<int:id_exploracion>', methods=['POST'])
@login_required
def eliminar_exploracion(id_exploracion):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE Exploracion SET estatus = 0 WHERE id_exploracion = %s", (id_exploracion,))
    conn.commit()
    
    cursor.close()
    conn.close()
    
    flash('Exploración eliminada exitosamente', 'success')
    return redirect(url_for('gestion_exploraciones'))
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