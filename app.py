from flask import Flask, render_template, request, redirect, url_for, session, flash
from config import DATABASE_CONFIG
import pyodbc

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Cambia esto por una clave segura


from datetime import datetime

@app.template_filter('datetimeformat')
def datetimeformat(value):
    if value:
        date_obj = datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S.%f")
        return date_obj.strftime("%d-%m-%Y %I:%M %p")  # Formato 12 horas con AM/PM
    return value


# Crear la función para conectarse a SQL Server
def get_db_connection():
    try:
        conn_str = (
            f"DRIVER={{{DATABASE_CONFIG['driver']}}};"
            f"SERVER={DATABASE_CONFIG['server']};"
            f"DATABASE={DATABASE_CONFIG['database']};"
            f"Trusted_Connection={DATABASE_CONFIG['trusted_connection']};"
        )
        return pyodbc.connect(conn_str)
    except pyodbc.Error as e:
        print(f"Error al conectar a la base de datos: {e}")
        return None

# Ruta principal
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form['correo']
        clave = request.form['password']

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

            
            flash('Inicio de session exitoso','success')

            if user.RolID == 1:  # Administrador
                return redirect(url_for('dashboard'))
            elif user.RolID == 2:  # Oficial de Seguridad
                return redirect(url_for('security_dashboard'))
            elif user.RolID == 3:  # Profesor
                return redirect(url_for('personal_administrativo'))
            elif user.RolID == 4:  # Estudiante
                return redirect(url_for('student_dashboard'))
        else:
            flash('Correo o contraseña incorrectos.', 'danger')

    return render_template('login.html')


# Ruta para cambiar contraseña
@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if request.method == 'POST':
        nueva_clave = request.form['new_password']
        user_id = session['user_id']

        # Validación: no puede contener 'Ulacit123'
        if 'Ulacit123' in nueva_clave:
            flash('No puedes ingresar una contraseña igual que diga Ulacit123.', 'danger')
            return redirect(url_for('change_password'))

        conn = get_db_connection()  
        cursor = conn.cursor()

        # Validación: contraseña repetida
        select_query = "SELECT Clave FROM Usuario WHERE UsuarioID = ?"
        cursor.execute(select_query, (user_id,))
        current_password = cursor.fetchone()
        if current_password and current_password[0] == nueva_clave:
            flash('No se pueden guardar claves repetidas.', 'danger')
            conn.close()
            return redirect(url_for('change_password'))

        # Actualización de contraseña
        try:
            update_query = "UPDATE Usuario SET Clave = ?, ClaveCambiada = 1 WHERE UsuarioID = ?"
            cursor.execute(update_query, (nueva_clave, user_id))
            conn.commit()
            flash('Contraseña cambiada exitosamente. Por favor inicia sesión de nuevo.', 'success')
        except Exception as e:
            flash('Ocurrió un error al cambiar la contraseña.', 'danger')
            print(e)
        finally:
            conn.close()

        return redirect(url_for('login'))

    return render_template('change_password.html')

# DAHSBOARD SECURITY 

@app.route('/select_parqueo', methods=['GET', 'POST'])
def select_parqueo():
    if 'user_role' in session and session['user_role'] == 2:
        conn = get_db_connection()
        cursor = conn.cursor()

        if request.method == 'POST':
            parqueo_id = request.form.get('parqueo_id')
            if parqueo_id:
                session['selected_parqueo'] = parqueo_id  # Guardar en la sesión
                flash('Parqueo seleccionado correctamente.', 'success')
                return redirect(url_for('security_dashboard'))  # Redirigir al dashboard
            else:
                flash('Por favor selecciona un parqueo.', 'danger')

        # Obtener lista de parqueos disponibles
        cursor.execute("SELECT ParqueoID, Nombre_Parqueo FROM Parqueo")
        parqueos = cursor.fetchall()
        conn.close()

        return render_template('select_parqueo.html', parqueos=parqueos, user_name=session.get('user_name'))
    else:
        flash('No tienes permisos para acceder a esta página.', 'danger')
        return redirect(url_for('login'))
    
#DASHBOARD SEGURIDAD

@app.route('/security_dashboard', methods=['GET', 'POST'])
def security_dashboard():
    if 'user_role' in session and session['user_role'] == 2:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Revisar si el usuario quiere "volver" a seleccionar un parqueo
        if request.args.get('action') == 'reset':
            session.pop('selected_parqueo', None)
            return redirect(url_for('select_parqueo'))

        # Seleccionar el parqueo
        if 'selected_parqueo' not in session:
            flash('Primero debes seleccionar un parqueo.', 'warning')
            return redirect(url_for('select_parqueo'))

        parqueo_id = session.get('selected_parqueo')

        # Obtener detalles del parqueo
        cursor.execute(
            """
            SELECT Nombre_Parqueo, Ubicacion, Espacios_Carros, Espacios_Moto, Espacios_Ley7600
            FROM Parqueo WHERE ParqueoID = ?
            """,
            (parqueo_id,)
        )
        parqueo = cursor.fetchone()

        # Calcular espacios ocupados y disponibles
        cursor.execute(
            """
            SELECT COUNT(*) FROM Vehiculo
            WHERE ParqueoID = ? AND Estado = 'ocupado' AND Tipo = 'carro' AND UsaEspacioLey7600 = 0
            """,
            (parqueo_id,)
        )
        carros_ocupados = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*) FROM Vehiculo
            WHERE ParqueoID = ? AND Estado = 'ocupado' AND Tipo = 'moto'
            """,
            (parqueo_id,)
        )
        motos_ocupados = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*) FROM Vehiculo
            WHERE ParqueoID = ? AND Estado = 'ocupado' AND UsaEspacioLey7600 = 1
            """,
            (parqueo_id,)
        )
        ley7600_ocupados = cursor.fetchone()[0]

        espacios_disponibles = {
            'carros': max(0, parqueo[2] - carros_ocupados),
            'motos': max(0, parqueo[3] - motos_ocupados),
            'ley7600': max(0, parqueo[4] - ley7600_ocupados)
        }

        if request.method == 'POST':
            # Verificar ingreso de vehículo
            if 'NumeroPlaca' in request.form:
                NumeroPlaca = request.form['NumeroPlaca']
                tipo = request.form['tipo']
                usa_ley7600 = request.form.get('ley7600') == 'si'

                # Verificar si el vehículo ya está ocupado en otro parqueo
                cursor.execute(
                    """
                    SELECT ParqueoID FROM Vehiculo
                    WHERE NumeroPlaca = ? AND Tipo = ? AND Estado = 'ocupado' AND ParqueoID != ?
                    """,
                    (NumeroPlaca, tipo, parqueo_id)
                )
                vehiculo_en_otro_parqueo = cursor.fetchone()

                if vehiculo_en_otro_parqueo:
                    flash(f'El vehículo con placa {NumeroPlaca} ya está registrado en otro parqueo.', 'danger')
                else:
                    # Verificar si el vehículo está registrado en la base de datos
                    cursor.execute(
                        """
                        SELECT VehiculoID FROM Vehiculo
                        WHERE NumeroPlaca = ? AND Tipo = ?
                        """,
                        (NumeroPlaca, tipo)
                    )
                    vehiculo_existente = cursor.fetchone()

                    if not vehiculo_existente:
                        # Consultar si el vehículo ha ingresado previamente sin estar registrado
                        cursor.execute(
                            """
                            SELECT COUNT(*) FROM BitacoraParqueo
                            WHERE NumeroPlaca = ? AND EstadoIngreso = 0
                            """,
                            (NumeroPlaca,)
                        )
                        intentos_no_registrado = cursor.fetchone()[0]

                        if intentos_no_registrado >= 1:
                            flash('El vehículo debe estar registrado para volver a ingresar.', 'danger')
                        else:
                            # Permitir ingreso por única vez sin estar registrado
                            cursor.execute(
                                """
                                INSERT INTO BitacoraParqueo (VehiculoID, NumeroPlaca, Fecha, TipoMovimiento, EstadoIngreso)
                                VALUES (NULL, ?, GETDATE(), 'Ingreso', 0)
                                """,
                                (NumeroPlaca,)
                            )
                            conn.commit()
                            flash(f'El vehículo con placa {NumeroPlaca} ingresó como no registrado. Este será el único ingreso permitido sin registro.', 'warning')
                    else:
                        # Determinar el tipo de espacio y verificar disponibilidad
                        if tipo == 'carro' and usa_ley7600:
                            espacio_tipo = 'ley7600'
                        elif tipo == 'carro':
                            espacio_tipo = 'carros'
                        elif tipo == 'moto':
                            espacio_tipo = 'motos'

                        if espacios_disponibles[espacio_tipo] > 0:
                            vehiculo_id = vehiculo_existente[0]
                            cursor.execute(
                                """
                                UPDATE Vehiculo
                                SET Estado = 'ocupado', ParqueoID = ?, UsaEspacioLey7600 = ?
                                WHERE VehiculoID = ?
                                """,
                                (parqueo_id, usa_ley7600, vehiculo_id)
                            )
                            conn.commit()
                            cursor.execute(
                                """
                                INSERT INTO BitacoraParqueo (VehiculoID, NumeroPlaca, Fecha, TipoMovimiento, EstadoIngreso)
                                VALUES (?, ?, GETDATE(), 'Ingreso', 1)
                                """,
                                (vehiculo_id, NumeroPlaca)
                            )
                            conn.commit()
                            flash(f'Vehículo con placa {NumeroPlaca} registrado con éxito.', 'success')
                        else:
                            flash('No hay espacios disponibles para este tipo de vehículo.', 'danger')

            # Retirar vehículo
            elif 'retirar_placa' in request.form:
                retirar_placa = request.form['retirar_placa']
                tipo_retirar = request.form.get('tipo_retirar')

                cursor.execute(
                    """
                    SELECT VehiculoID FROM Vehiculo
                    WHERE NumeroPlaca = ? AND Tipo = ? AND ParqueoID = ? AND Estado = 'ocupado'
                    """,
                    (retirar_placa, tipo_retirar, parqueo_id)
                )
                vehiculo = cursor.fetchone()

                if vehiculo:
                    vehiculo_id = vehiculo[0]
                    cursor.execute(
                        """
                        UPDATE Vehiculo
                        SET Estado = 'libre', ParqueoID = NULL
                        WHERE VehiculoID = ?
                        """,
                        (vehiculo_id,)
                    )
                    cursor.execute(
                        """
                        INSERT INTO BitacoraParqueo (VehiculoID, NumeroPlaca, Fecha, TipoMovimiento, EstadoIngreso)
                        VALUES (?, ?, GETDATE(), 'Egreso', 1)
                        """,
                        (vehiculo_id, retirar_placa)
                    )
                    conn.commit()
                    flash(f'Vehículo con placa {retirar_placa} retirado exitosamente.', 'success')
                else:
                    flash('El vehículo no está registrado en este parqueo.', 'danger')

        # Obtener lista de vehículos en el parqueo
        cursor.execute(
            """
            SELECT NumeroPlaca, Tipo, UsaEspacioLey7600
            FROM Vehiculo
            WHERE ParqueoID = ? AND Estado = 'ocupado'
            """,
            (parqueo_id,)
        )
        vehiculos_en_parqueo = cursor.fetchall()

        conn.close()

        # Determinar el estado del semáforo
        semaforo_general = 'rojo' if all(space == 0 for space in espacios_disponibles.values()) else 'verde'

        return render_template(
            'security_dashboard.html',
            parqueo=parqueo,
            espacios_disponibles=espacios_disponibles,
            vehiculos_en_parqueo=vehiculos_en_parqueo,
            semaforo_general=semaforo_general,
            user_name=session['user_name']
        )
    else:
        flash('No tienes permisos para acceder a esta página.', 'danger')
        return redirect(url_for('login'))

#BITACORA
@app.route('/bitacora', methods=['GET', 'POST'])
def bitacora():
    if 'user_role' in session and session['user_role'] in [1, 2]:  # Administrador o Seguridad
        conn = get_db_connection()
        cursor = conn.cursor()

        # Obtener el filtro de mes desde el formulario
        selected_month = request.form.get('month') if request.method == 'POST' else None
        selected_year = request.form.get('year') if request.method == 'POST' else None

        # Consulta SQL con filtro opcional por mes y año
        query = """
            SELECT B.BitacoraID, 
                   COALESCE(B.NumeroPlaca, 'No Registrada') AS NumeroPlaca, 
                   B.Fecha, 
                   B.TipoMovimiento, 
                   CASE WHEN B.EstadoIngreso = 1 THEN 'Registrado' ELSE 'No Registrado' END AS EstadoIngreso
            FROM BitacoraParqueo B
            LEFT JOIN Vehiculo V ON B.VehiculoID = V.VehiculoID
        """

        params = []
        if selected_month and selected_year:
            query += " WHERE MONTH(B.Fecha) = ? AND YEAR(B.Fecha) = ?"
            params.extend([selected_month, selected_year])

        query += " ORDER BY B.Fecha DESC"

        cursor.execute(query, params)
        registros = cursor.fetchall()

        conn.close()
        return render_template('bitacora.html', bitacoras=registros, selected_month=selected_month, selected_year=selected_year)
    else:
        flash('No tienes permisos para acceder a esta página.', 'danger')
        return redirect(url_for('login'))


# DASHBOARD ESTUDIANTE
@app.route('/student_dashboard', methods=['GET', 'POST'])
def student_dashboard():
    if 'user_role' in session and session['user_role'] == 4:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Obtener vehículos del usuario
        cursor.execute("SELECT * FROM Vehiculo WHERE UsuarioID = ?", (session['user_id'],))
        vehiculos = cursor.fetchall()

        # Filtro de mes y año desde el formulario
        selected_month = request.form.get('month') if request.method == 'POST' else None
        selected_year = request.form.get('year') if request.method == 'POST' else None

        # Obtener el historial de ingresos para los vehículos del estudiante
        query = """
            SELECT B.BitacoraID, 
                   COALESCE(B.NumeroPlaca, 'No Registrada') AS NumeroPlaca, 
                   B.Fecha, 
                   B.TipoMovimiento, 
                   CASE WHEN B.EstadoIngreso = 1 THEN 'Registrado' ELSE 'No Registrado' END AS EstadoIngreso
            FROM BitacoraParqueo B
            WHERE B.NumeroPlaca IN (
                SELECT NumeroPlaca FROM Vehiculo WHERE UsuarioID = ?
            )
        """
        params = [session['user_id']]

        if selected_month and selected_year:
            query += " AND MONTH(B.Fecha) = ? AND YEAR(B.Fecha) = ?"
            params.extend([selected_month, selected_year])

        query += " ORDER BY B.Fecha DESC"

        cursor.execute(query, params)
        historial = cursor.fetchall()

        conn.close()

        return render_template(
            'student_dashboard.html', 
            user_name=session['user_name'], 
            vehiculos=vehiculos, 
            historial=historial, 
            selected_month=selected_month, 
            selected_year=selected_year
        )
    else:
        flash('No tienes permisos para acceder a esta página.', 'danger')
        return redirect(url_for('login'))

# DASHBOARD ADMINISTRADOR


@app.route('/dashboard')
def dashboard():
    if 'user_role' in session and session['user_role'] == 1:
        return render_template('dashboard.html', user_name=session['user_name'])
    else:
        flash('No tienes permisos para acceder a esta página.', 'danger')
        return redirect(url_for('login'))



# LISTAR USUARIOS 

@app.route('/admin/menu', methods=['GET', 'POST'])
def menu():
    if 'user_role' in session and session['user_role'] == 1:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Filtrado por rol y búsqueda
        role_filter = request.args.get('role')
        search_query = request.args.get('search')
        
        query = """
            SELECT Usuario.UsuarioID, Usuario.Nombre, Usuario.Correo, Rol.NombreRol
            FROM Usuario
            JOIN Rol ON Usuario.RolID = Rol.RolID
            WHERE 1=1
            """
        
        params = []

        if role_filter:
            query += " AND Usuario.RolID = ?"
            params.append(role_filter)
        
        if search_query:
            query += " AND (Usuario.Nombre LIKE ? OR Usuario.Correo LIKE ?)"
            params.extend([f"%{search_query}%", f"%{search_query}%"])

        cursor.execute(query, params)
        users = cursor.fetchall()

        return render_template('menu.html', users=users, selected_role=role_filter, search_query=search_query)
    else:
        flash('No tienes permisos para acceder a esta página.')
        return redirect(url_for('login'))


# PERFIL DE USUARIO

@app.route('/admin/user/<int:user_id>', methods=['GET', 'POST'])
def user_profile(user_id):
    if 'user_role' in session and session['user_role'] == 1:
        conn = get_db_connection()
        cursor = conn.cursor()

        if request.method == 'POST':
            nombre = request.form['nombre']
            correo = request.form['correo']
            identificacion = request.form['identificacion']
            rol = request.form['rol']

            # Actualizar datos del usuario
            cursor.execute("""
                UPDATE Usuario SET Nombre = ?, Correo = ?, Identificacion = ?, RolID = ?
                WHERE UsuarioID = ?
            """, (nombre, correo, identificacion, rol, user_id))
            conn.commit()
            flash('Perfil de usuario actualizado.')
            return redirect(url_for('user_profile', user_id=user_id))

        # Obtener detalles del usuario
        cursor.execute("SELECT UsuarioID, Nombre, Correo, Identificacion, RolID FROM Usuario WHERE UsuarioID = ?", (user_id,))
        user = cursor.fetchone()

        # Obtener vehículos asociados
        cursor.execute("SELECT * FROM Vehiculo WHERE UsuarioID = ?", (user_id,))
        vehicles = cursor.fetchall()

        return render_template('user_profile.html', user=user, vehicles=vehicles)
    else:
        flash('No tienes permisos para acceder a esta página.')
        return redirect(url_for('login'))



#AGREGAR VEHICULO A UN PERFIL


@app.route('/admin/user/<int:user_id>/add_vehicle', methods=['GET', 'POST'])
def add_vehicle(user_id):
    if 'user_role' in session and session['user_role'] == 1:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Verificar si el usuario ya tiene dos vehículos registrados
        cursor.execute("SELECT COUNT(*) FROM Vehiculo WHERE UsuarioID = ?", (user_id,))
        vehicle_count = cursor.fetchone()[0]

        if vehicle_count >= 2:
            flash('No puedes registrar más de dos vehículos.', 'danger')
            return redirect(url_for('user_profile', user_id=user_id))

        if request.method == 'POST':
            marca = request.form['marca']
            color = request.form['color']
            numero_placa = request.form['numero_placa']
            tipo = request.form['tipo']
            UsaEspacioLey7600 = request.form.get('UsaEspacioLey7600') == 'on'
            
            # Validar que no exista un vehículo del mismo tipo con la misma NumeroPlaca
            cursor.execute("""
                SELECT COUNT(*) FROM Vehiculo 
                WHERE NumeroPlaca = ? AND Tipo = ?
            """, (numero_placa, tipo))
            existing_vehicle_count = cursor.fetchone()[0]

            if existing_vehicle_count > 0:
                flash('Ya existe un vehículo de este tipo con esa placa.', 'danger')
                return redirect(url_for('add_vehicle', user_id=user_id))

    
            # Registrar vehículo
            cursor.execute("""
                INSERT INTO Vehiculo (Marca, Color, NumeroPlaca, Tipo, UsuarioID, UsaEspacioLey7600, Estado)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (marca, color, numero_placa, tipo, user_id, UsaEspacioLey7600))
            conn.commit()

            flash('Vehículo registrado exitosamente.', 'success')
            return redirect(url_for('user_profile', user_id=user_id))

        return render_template('add_vehicle.html', user_id=user_id)
    else:
        flash('No tienes permisos acceder a esta página.')
        return redirect(url_for('login'))
    



#VER VEHICULOS 

@app.route('/user/<int:user_id>/vehicles')
def user_vehicles(user_id):
    if 'user_id' in session:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Obtener el nombre del usuario y los vehículos asociados
        cursor.execute("SELECT Nombre FROM Usuario WHERE UsuarioID = ?", (user_id,))
        user = cursor.fetchone()
        
        cursor.execute("SELECT Marca, Color, NumeroPlaca, UsaEspacioLey7600 Tipo FROM Vehiculo WHERE UsuarioID = ?", (user_id,))
        vehicles = cursor.fetchall()

        # Si el usuario actual es el dueño del perfil o es administrador, puede ver los vehículos
        if session['user_id'] == user_id or session['user_role'] == 1:
            return render_template('user_vehicles.html', user=user, vehicles=vehicles)
        else:
            flash('No tienes permisos para ver esta información.', 'danger')
            return redirect(url_for('dashboard'))
    else:
        flash('Por favor inicia sesión para continuar.', 'danger')
        return redirect(url_for('login'))
    


#REGISTRAR USUARIOS


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
            
            # Consulta de verificación corregida
            check_query = """
            SELECT COUNT(*) FROM Usuario WHERE correo = ? AND identificacion = ?
            """
            cursor.execute(check_query, (correo, identificacion))
            result = cursor.fetchone()

            if result[0] > 0:
                flash("No se puede usar correos ni identificaciones repetidas.", "danger")
                return redirect(url_for('register_user'))

            # Inserción de usuario
            insert_query = """
                INSERT INTO Usuario (Nombre, Correo, FechaNacimiento, Identificacion, Clave, ClaveCambiada, RolID)
                VALUES (?, ?, ?, ?, 'Ulacit123', 0, ?)
            """
            cursor.execute(insert_query, (nombre, correo, fecha_nacimiento, identificacion, rol))
            conn.commit()

            flash('Usuario registrado exitosamente. La contraseña predeterminada es: Ulacit123', 'success')
            return redirect(url_for('register_user'))
        
        except pyodbc.IntegrityError as e: 
            # Error específico para clave única duplicada
            if e.args[0] == '23000' and ('2627' in e.args[1] or '2601' in e.args[1]):
                flash("No se puede usar correos ni identificaciones repetidas.", 'danger')
            else:
                flash("Error al registrar usuario.", 'danger')
        except Exception as e:
            flash("Error al registrar usuario.", 'danger')
            return render_template('register_user.html')

    # Para solicitudes GET (sin mensaje de error o éxito)
    return render_template('register_user.html', message=None, icon=None)





#REGISTRAR PARQUEOS

@app.route("/admin/register_parqueo", methods=["GET", "POST"])
def register_parqueo():
    if request.method == 'POST':
        # Obtiene los datos del formulario
        Nombre_parqueo = request.form.get("Nombre_parqueo")
        Ubicacion = request.form.get("Ubicacion")
        
        # Aseguramos los límites para cada tipo de espacio entre 1 y 50
        try:
            Espacios_Carros = max(0, min(int(request.form.get("Espacios_Carros") or 1), 50))
            Espacios_Moto = max(0, min(int(request.form.get("Espacios_Moto") or 1), 50))
            Espacios_Ley7600 = max(0, min(int(request.form.get("Espacios_Ley7600") or 1), 50))

        
        except ValueError:
            
            flash("Los valores ingresados deben ser números enteros.", "danger")
            return redirect(url_for('register_parqueo'))

        # Validación de campos obligatorios
        if not Nombre_parqueo or not Ubicacion:
            flash("Todos los campos son obligatorios.", "danger")
            return redirect(url_for('register_parqueo'))

        try:
            # Conecta a la base de datos
            conn = get_db_connection()
            cursor = conn.cursor()

            check_query = """
            SELECT COUNT(*) FROM Parqueo WHERE Nombre_Parqueo = ? 
            """
            cursor.execute(check_query, (Nombre_parqueo))
            result_nombre = cursor.fetchone()

            if result_nombre[0] > 0:
                # Si ya existe, muestra el mensaje de error y redirige
                flash("No se pueden agregar nombres y ubicaciones repetidas. No es válido!!", "danger")
                return redirect(url_for('register_parqueo'))

            check_query = """
            SELECT COUNT(*) FROM Parqueo WHERE Ubicacion = ?
            """
            cursor.execute(check_query, (Ubicacion))
            result_ubicacion = cursor.fetchone()

            if result_ubicacion[0] > 0:

                # Si ya existe, muestra el mensaje de error y redirige
                flash("No se pueden agregar nombres y ubicaciones repetidas. No es válido!", "danger")
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
    
    return render_template("register_parqueo.html")


#BOTON DE BORRAR

@app.route('/admin/user/<int:user_id>/delete_vehicle/<int:vehicle_id>', methods=['POST'])
def delete_vehicle(user_id, vehicle_id):
    if 'user_role' in session and session['user_role'] == 1:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Ejecutar la eliminación del vehículo
        cursor.execute("DELETE FROM Vehiculo WHERE VehiculoID = ? AND UsuarioID = ?", (vehicle_id, user_id))
        conn.commit()
        
        flash('Vehículo eliminado exitosamente.', 'success')
        return redirect(url_for('user_profile', user_id=user_id))
    else:
        flash('No tienes permisos para realizar esta acción.', 'danger')
        return redirect(url_for('login'))








# Ruta para cerrar sesión
@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión exitosamente.', 'success')
    return redirect(url_for('login'))








if __name__ == '__main__':
    app.run(debug=True)
