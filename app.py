from flask import Flask, render_template, request, redirect, url_for, session, flash
from config import DATABASE_CONFIG
import pyodbc
print("Iniciando aplicación Flask...")

app = Flask(__name__)
app.secret_key = 'your_secret_key'  

# Acá creamos la función para conectarse a SQL Server
def get_db_connection():
    conn_str = (
        f"DRIVER={{{DATABASE_CONFIG['driver']}}};"
        f"SERVER={DATABASE_CONFIG['server']};"
        f"DATABASE={DATABASE_CONFIG['database']};"
        f"Trusted_Connection={DATABASE_CONFIG['trusted_connection']};"
    )
    return pyodbc.connect(conn_str)

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            correo = request.form['correo']
            clave = request.form['password']

            # Conectamos a la base de datos y verificamos credenciales
            conn = get_db_connection()
            cursor = conn.cursor()
            query = "SELECT UsuarioID, Nombre, RolID, Clave, ClaveCambiada FROM Usuario WHERE Correo = ?"
            cursor.execute(query, (correo,))
            user = cursor.fetchone()

            if user and user.Clave == clave:
                session['user_id'] = user.UsuarioID
                session['user_name'] = user.Nombre
                session['user_role'] = user.RolID

                if not user.ClaveCambiada:
                    return redirect(url_for('change_password'))

                
                # En este IF se redirige dependiendo del rol del usuario
                if session['user_role'] == 1:  # Administrador
                    return redirect(url_for('dashboard'))
                else:  # Usuario normal
                    return redirect(url_for('user_dashboard'))
            else:
                flash('Correo o contraseña incorrectos.')
        except KeyError as e:
            flash(f"Error: {e}")
    
    return render_template('login.html')


@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if request.method == 'POST':
        nueva_clave = request.form['new_password']
        user_id = session['user_id']
        
        # Verificar si la nueva contraseña es igual a la predeterminada
        if nueva_clave == "Ulacit123":
            flash("No puedes usar la contraseña predeterminada. Por favor, elige una nueva." ,"danger")
            return render_template('change_password.html')
        
        # Conecta a la base de datos
        conn = get_db_connection()
        cursor = conn.cursor()

        # Actualizamos la contraseña
        update_query = "UPDATE Usuario SET Clave = ?, ClaveCambiada = 1 WHERE UsuarioID = ?"
        cursor.execute(update_query, (nueva_clave, user_id))
        conn.commit()

        flash('Contraseña cambiada exitosamente. Por favor inicia sesión de nuevo.')
        return redirect(url_for('login'))
    
    # Renderizar la plantilla en caso de una solicitud GET
    return render_template('change_password.html')

   

@app.route('/dashboard')
def dashboard():
    if 'user_role' in session and session['user_role'] == 1:  # Verificamos si el usuario es administrador
        return render_template('dashboard.html', user_name=session['user_name'], user_role=session['user_role'])
    else:
        flash('No tienes permisos para acceder a esta página.', 'danger')
        return redirect(url_for('login'))



@app.route('/user_dashboard')
def user_dashboard():
    if 'user_role' in session and session['user_role'] != 1:  # Verificamos si el usuario no es administrador
        return render_template('user_dashboard.html', user_name=session['user_name'], user_role=session['user_role'])
    else:
        flash('No tienes permisos para acceder a esta página.', 'danger')
        return redirect(url_for('login'))
    

    #Administrador 

@app.route("/admin/register_parqueo", methods=["GET", "POST"])
def register_parqueo():
    if request.method == 'POST':
        # Obtiene los datos del formulario
        Nombre_parqueo = request.form.get("Nombre_parqueo")
        Ubicacion = request.form.get("Ubicacion")
        Espacios_Carros = int(request.form.get("Espacios_Carros") or 0)
        Espacios_Moto = int(request.form.get("Espacios_Moto") or 0)
        Espacios_Ley7600 = int(request.form.get("Espacios_Ley7600") or 0)

        # Validación de campos obligatorios
        if not Nombre_parqueo or not Ubicacion:
            flash("Todos los campos son obligatorios.", "danger")
            return redirect(url_for('register_parqueo'))

        

        try:
            # Conecta a la base de datos
            conn = get_db_connection()
            cursor = conn.cursor()


            check_query = """
            SELECT COUNT(*) FROM Parqueo WHERE Nombre_Parqueo = ? AND Ubicacion = ?
                    """
            cursor.execute(check_query, (Nombre_parqueo, Ubicacion))
            result = cursor.fetchone()

            if result[0] > 0:
                # Si ya existe, muestra el mensaje de error y redirige
                flash("No se pueden agregar nombres y ubicaciones repetidas. No es válido!!", "danger")
                return redirect(url_for('register_parqueo'))
            
            # Consulta de inserción
            insert_query = """
                INSERT INTO Parqueo (Nombre_Parqueo, Ubicacion, Espacios_Carros, Espacios_Moto, Espacios_Ley7600)
                VALUES (?, ?, ?, ?, ?)
            """
            cursor.execute(insert_query, (Nombre_parqueo, Ubicacion, Espacios_Carros, Espacios_Moto, Espacios_Ley7600))
            conn.commit()

            # Mensaje de éxito
            flash('Parqueo registrado correctamente.', 'success')
        
        except Exception as e:
            flash(f'Error al registrar parqueo: {e}', 'danger')
        
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for('register_parqueo'))
    # 
    return render_template("register_parqueo.html")



@app.route('/admin/register', methods=['GET', 'POST'])
def register_user():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        correo = request.form.get('correo')
        fecha_nacimiento = request.form.get('fecha_nacimiento')
        identificacion = request.form.get('identificacion')
        rol = request.form.get('rol')

        try:

            conn = get_db_connection()
            cursor = conn.cursor()


            # Insertamos el la BSD un nuevo usuario con clave predeterminada "Ulacit123"
            insert_query = """
                INSERT INTO Usuario (Nombre, Correo, FechaNacimiento, Identificacion, Clave, ClaveCambiada, RolID)
                VALUES (?, ?, ?, ?, 'Ulacit123', 0, ?)
            """
            cursor.execute(insert_query, (nombre, correo, fecha_nacimiento, identificacion, rol))
            conn.commit()

            flash('Usuario registrado exitosamente. La contraseña predeterminada es: Ulacit123', 'success')
            return redirect(url_for('register_user'))
        
        except pyodbc.IntegrityError as e:
            # Captura específica del error de duplicado en SQL Server
            # Es decir todos los que son uniques en nuestras tablas
            if e.args[0] == '23000' and ('2627' in e.args[1] or '2601' in e.args[1]):
                
                flash("No se puede registrar otro usuario con el mismo correo.", 'danger')
            else:
                flash(f"Error al registrar usuario: {e}", 'danger')
        except Exception as e:
            flash(f"Error al registrar usuario: {e}", 'danger')
            return render_template('register_user.html')

    
        except pyodbc.IntegrityError as e:
            # Si el error es por violación de unicidad (duplicado)
            if e.args[0] == '23000' and ('2627' in e.args[1] or '2601' in e.args[1]):
                # Mensaje de error específico para duplicados
                return render_template('register_user.html', message="No se puede registrar otro usuario con el mismo correo o identificación.", icon="error")
            else:
                # Mensaje de error general
                return render_template('register_user.html', message=f"Error al registrar usuario: {e}", icon="error")
        except Exception as e:
            return render_template('register_user.html', message=f"Error al registrar usuario: {e}", icon="error")

    # Para solicitudes GET (sin mensaje de error o éxito)
    return render_template('register_user.html', message=None, icon=None)


@app.route('/logout')
def logout():
    session.clear()  # Nos salimos del usuario y aparecemos de nuevo en Login
    flash('Has cerrado sesión exitosamente.', 'success')
    return redirect(url_for('login'))



if __name__ == '__main__':
    app.run(debug=True)
