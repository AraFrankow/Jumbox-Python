from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
import os
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from app import bcrypt
from app.utils import get_conn

auth_bp = Blueprint('auth', __name__, template_folder='../../templates/auth')

# En producción esto no es necesario, pero no rompe.
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
REDIRECT_URI_LOCAL = "http://127.0.0.1:5000/auth/callback"
REDIRECT_URI_PROD = "https://jumbox-python.onrender.com/auth/callback"


def create_flow(state=None):
    if request.host.startswith("127.0.0.1") or request.host.startswith("localhost"):
        redirect_uri = REDIRECT_URI_LOCAL
    else:
        redirect_uri = REDIRECT_URI_PROD

    return Flow.from_client_config(
        client_config={
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI_LOCAL, REDIRECT_URI_PROD],  # acá ya queda bien
            }
        },
        scopes=[
            "openid",
            "https://www.googleapis.com/auth/userinfo.profile",
        ],
        state=state,
        redirect_uri=redirect_uri,
    )


@auth_bp.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form['nombre']
        tel = request.form['tel']
        direccion = request.form['direccion']
        contra = request.form['contra']
        confirmar = request.form['confirmar']

        if contra != confirmar:
            flash('Las contraseñas no coinciden', 'error')
            return render_template('registro.html', nombre=nombre, tel=tel, direccion=direccion)

        hash_contra = bcrypt.generate_password_hash(contra).decode('utf-8')

        try:
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO cliente (nombre, direccion, telefono, contrasena, tipo)
                VALUES (?, ?, ?, ?, 'usuario')
            """, (nombre, direccion, tel, hash_contra))
            conn.commit()
            conn.close()

            flash("Registro exitoso", "success")
            return redirect(url_for('auth.login'))
        except Exception:
            flash("El teléfono ya está registrado o ocurrió un error.", "error")
            return redirect(url_for('auth.registro'))

    return render_template('registro.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        tel = request.form['tel']
        contra = request.form['contra']

        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id_cliente, nombre, contrasena, tipo
            FROM cliente
            WHERE telefono = ?
        """, (tel,))
        cliente = cursor.fetchone()
        conn.close()

        if cliente and bcrypt.check_password_hash(cliente[2], contra):
            session['id_cliente'] = cliente[0]
            session['nombre'] = cliente[1]
            session['tipo'] = cliente[3]

            flash("Inicio de sesión exitoso", "success")

            if cliente[3] == 'sucursal':
                return redirect(url_for('sucursal.panel_sucursal'))
            elif cliente[3] == 'admin':
                return redirect(url_for('admin.admin'))
            else:
                return redirect(url_for('main.home'))

        flash("Credenciales incorrectas", "error")
        return render_template('login.html', tel=tel)

    return render_template('login.html')


@auth_bp.route("/logingoogle")
def logingoogle():
    try:
        flow = create_flow()
    except RuntimeError as e:
        # Si faltan env vars, vas a ver este mensaje en el navegador
        return str(e), 500

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )
    session["state"] = state
    return redirect(authorization_url)


@auth_bp.route("/auth/callback")
def callback():
    # Recuperamos el state de sesión
    state = session.get("state")
    if not state:
        flash("Sesión de Google no válida o expirada. Probá nuevamente.", "error")
        return redirect(url_for("auth.login"))

    try:
        flow = create_flow(state=state)
    except RuntimeError as e:
        return str(e), 500

    try:
        flow.fetch_token(authorization_response=request.url)
    except Exception as e:
        print("Error al obtener el token de Google:", e)
        flash("Ocurrió un error al autenticar con Google.", "error")
        return redirect(url_for("auth.login"))

    credentials = flow.credentials
    request_session = google_requests.Request()

    try:
        id_info = id_token.verify_oauth2_token(
            credentials.id_token,
            request_session,
            GOOGLE_CLIENT_ID
        )
    except Exception as e:
        print("Error al verificar el ID token de Google:", e)
        flash("No se pudo verificar la autenticación de Google.", "error")
        return redirect(url_for("auth.login"))

    phone_number = id_info.get("phone_number")
    nombre_google = id_info.get("name", "Usuario Google")

    # Si Google no devuelve teléfono, pedimos que lo ingrese
    if not phone_number:
        session["google_temp_id"] = id_info.get("sub")
        session["nombre_google"] = nombre_google
        return redirect(url_for("auth.pedir_telefono"))

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id_cliente, nombre, tipo FROM cliente WHERE telefono = ?",
        (phone_number,)
    )
    cliente = cursor.fetchone()

    if not cliente:
        cursor.execute(
            "INSERT INTO cliente (nombre, direccion, telefono, contrasena, tipo) "
            "VALUES (?, ?, ?, ?, ?)",
            (nombre_google, "", phone_number, "", "usuario")
        )
        conn.commit()
        cursor.execute(
            "SELECT id_cliente, nombre, tipo FROM cliente WHERE telefono = ?",
            (phone_number,)
        )
        cliente = cursor.fetchone()

    conn.close()

    session["id_cliente"] = cliente[0]
    session["nombre"] = cliente[1]
    session["tipo"] = cliente[2]

    flash("Inicio de sesión exitoso", "success")
    return redirect(url_for("main.home"))


@auth_bp.route("/pedir-telefono", methods=["GET", "POST"])
def pedir_telefono():
    if request.method == "POST":
        telefono = request.form["telefono"]
        google_id = session.get("google_temp_id")
        nombre_google = session.get("nombre_google", "Usuario Google")

        if not google_id:
            flash("Error: sesión de Google no válida.", "error")
            return redirect(url_for("auth.login"))

        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id_cliente, nombre, tipo FROM cliente WHERE telefono = ?",
            (telefono,)
        )
        cliente = cursor.fetchone()

        if cliente:
            nombre_existente = cliente[1]
            if nombre_existente != nombre_google:
                conn.close()
                flash("El número de teléfono ya está asociado a otra cuenta. Las credenciales no coinciden.", "error")
                return redirect(url_for("auth.login"))
        else:
            cursor.execute(
                "INSERT INTO cliente (nombre, direccion, telefono, contrasena, tipo) "
                "VALUES (?, ?, ?, ?, ?)",
                (nombre_google, "", telefono, "", "usuario")
            )
            conn.commit()
            cursor.execute(
                "SELECT id_cliente, nombre, tipo FROM cliente WHERE telefono = ?",
                (telefono,)
            )
            cliente = cursor.fetchone()

        conn.close()

        session["id_cliente"] = cliente[0]
        session["nombre"] = cliente[1]
        session["tipo"] = cliente[2]

        flash("Inicio de sesión exitoso", "success")
        return redirect(url_for("main.home"))

    return render_template("pedir_telefono.html")


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada correctamente', 'success')
    return redirect(url_for('main.home'))