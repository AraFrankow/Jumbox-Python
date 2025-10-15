from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
from flask_bcrypt import Bcrypt

# telefono admin: 12345678
# contraseña admin: Admin1234
# telefono usuario1: 87654321
# contraseña usuario1: Usuario1234

app = Flask(__name__)
app.secret_key = 'clave_secreta_super_segura'
bcrypt = Bcrypt(app)
DB_NAME = "jumbox.db"


# =========================
# Rutas base existentes
# =========================
@app.route('/')
def home():
    return render_template('index.html')

@app.errorhandler(404)
def pagina_no_encontrada(e):
    return render_template('404.html'), 404

@app.errorhandler(405)
def pagina_no_encontrada2(e):
    return render_template('404.html'), 405

@app.route('/registro', methods=['GET', 'POST'])
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
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO cliente (nombre, direccion, telefono, contrasena, tipo)
                VALUES (?, ?, ?, ?, 'usuario')
            """, (nombre, direccion, tel, hash_contra))
            conn.commit()
            conn.close()

            flash("Registro exitoso", "success")
            return redirect(url_for('registro'))
        except sqlite3.IntegrityError:
            flash("El telefono ya está registrado", "error")
            return redirect(url_for('registro'))

    return render_template('registro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        tel = request.form['tel']
        contra = request.form['contra']

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id_cliente, nombre, contrasena, tipo FROM cliente WHERE telefono = ?", (tel,))
        cliente = cursor.fetchone()
        conn.close()

        if cliente and bcrypt.check_password_hash(cliente[2], contra):
            session['id_cliente'] = cliente[0]
            session['nombre'] = cliente[1]
            session['tipo'] = cliente[3]
            flash("Inicio de sesión exitoso", "success")
            return redirect(url_for('home'))

        flash("Credenciales incorrectas", "error")
        return render_template('login.html', tel=tel)

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada correctamente', 'success')
    return redirect(url_for('home'))


# =========================
# Helpers de DB y Carrito
# =========================
def get_conn():
    """Conexión SQLite con row_factory y FK on."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def require_login_redirect():
    """Si no hay sesión, redirige a login y devuelve esa Response; si hay sesión, devuelve None."""
    if 'id_cliente' not in session:
        flash("Necesitás iniciar sesión.", "error")
        return redirect(url_for('login'))
    return None

def ensure_carrito_abierto(conn, id_cliente: int):
    """
    Busca el carrito del cliente (en tu esquema no hay estado).
    Si no existe, lo crea.
    """
    car = conn.execute(
        "SELECT * FROM carrito WHERE fk_cliente=? LIMIT 1",
        (id_cliente,)
    ).fetchone()
    if car:
        return car
    cur = conn.execute(
        "INSERT INTO carrito(fk_cliente) VALUES (?)",
        (id_cliente,)
    )
    return conn.execute(
        "SELECT * FROM carrito WHERE id_carrito=?",
        (cur.lastrowid,)
    ).fetchone()

def leer_items(conn, id_carrito: int):
    """
    Lee items del carrito junto con datos del producto.
    """
    rows = conn.execute("""
        SELECT
            pc.fk_producto              AS producto_id,
            p.nombre                    AS nombre,
            p.precio                    AS precio,
            pc.cantidad                 AS cantidad,
            (p.precio * pc.cantidad)    AS subtotal
        FROM producto_carrito pc
        JOIN producto p ON p.id_producto = pc.fk_producto
        WHERE pc.fk_carrito = ?
        ORDER BY p.nombre
    """, (id_carrito,)).fetchall()
    total = sum(r['subtotal'] for r in rows) if rows else 0.0
    return rows, total


# =========================
# Carrito (sin JS, adaptado a tu DB)
# =========================
@app.get('/carrito')
def carrito():
    # Login requerido
    resp = require_login_redirect()
    if resp: 
        return resp

    id_cliente = session['id_cliente']
    cliente = {"id_cliente": id_cliente, "nombre": session.get('nombre', 'Usuario')}

    with get_conn() as conn:
        car = ensure_carrito_abierto(conn, id_cliente)
        items, total = leer_items(conn, car['id_carrito'])

        # categorías solo si existe esa tabla (para el menú del header)
        try:
            categorias = [r['nombre'] for r in conn.execute("SELECT nombre FROM categoria").fetchall()]
        except sqlite3.Error:
            categorias = []

    return render_template(
        'carrito.html',
        cliente=cliente,
        categorias=categorias,
        items=items,
        total=total,
        metodos_pago=['EFECTIVO', 'TARJETA']
    )

@app.post('/carrito/items/update')
def carrito_actualizar_item():
    resp = require_login_redirect()
    if resp: 
        return resp

    id_cliente  = session['id_cliente']
    producto_id = request.form.get('producto_id', type=int)
    cantidad    = request.form.get('cantidad', type=int)

    if not producto_id or not cantidad or cantidad < 1:
        flash("Cantidad inválida.", "error")
        return redirect(url_for('carrito'))

    with get_conn() as conn:
        car = ensure_carrito_abierto(conn, id_cliente)

        # Existe el item?
        ex = conn.execute("""
            SELECT id_producto_carrito
            FROM producto_carrito
            WHERE fk_carrito=? AND fk_producto=?
        """, (car['id_carrito'], producto_id)).fetchone()

        if ex:
            conn.execute("""
                UPDATE producto_carrito
                SET cantidad=?
                WHERE id_producto_carrito=?
            """, (cantidad, ex['id_producto_carrito']))
        else:
            conn.execute("""
                INSERT INTO producto_carrito(fk_producto, fk_carrito, cantidad)
                VALUES (?,?,?)
            """, (producto_id, car['id_carrito'], cantidad))

    flash("Carrito actualizado.", "success")
    return redirect(url_for('carrito'))

@app.post('/carrito/items/remove')
def carrito_eliminar_item():
    resp = require_login_redirect()
    if resp: 
        return resp

    id_cliente  = session['id_cliente']
    producto_id = request.form.get('producto_id', type=int)
    if not producto_id:
        flash("Producto inválido.", "error")
        return redirect(url_for('carrito'))

    with get_conn() as conn:
        car = ensure_carrito_abierto(conn, id_cliente)
        conn.execute("""
            DELETE FROM producto_carrito
            WHERE fk_carrito=? AND fk_producto=?
        """, (car['id_carrito'], producto_id))

    flash("Producto eliminado.", "success")
    return redirect(url_for('carrito'))

@app.post('/carrito/checkout')
def carrito_checkout():
    resp = require_login_redirect()
    if resp: 
        return resp

    metodo_pago   = request.form.get('metodo_pago')
    observaciones = request.form.get('observaciones', '')  # por ahora no se guarda

    if metodo_pago not in ('EFECTIVO', 'TARJETA'):
        flash("Seleccioná un método de pago válido.", "error")
        return redirect(url_for('carrito'))

    id_cliente = session['id_cliente']

    with get_conn() as conn:
        car = ensure_carrito_abierto(conn, id_cliente)

        items = conn.execute("""
            SELECT pc.fk_producto AS producto_id, pc.cantidad, p.precio, p.stock
            FROM producto_carrito pc
            JOIN producto p ON p.id_producto = pc.fk_producto
            WHERE pc.fk_carrito=?
        """, (car['id_carrito'],)).fetchall()

        if not items:
            flash("Tu carrito está vacío.", "error")
            return redirect(url_for('carrito'))

        # Validar stock global (según tu schema)
        for it in items:
            if it['stock'] < it['cantidad']:
                flash("Stock insuficiente para uno o más productos.", "error")
                return redirect(url_for('carrito'))

        # Descontar stock y vaciar carrito (versión mínima con tu schema actual)
        for it in items:
            conn.execute("""
                UPDATE producto
                SET stock = stock - ?
                WHERE id_producto = ?
            """, (it['cantidad'], it['producto_id']))

        conn.execute("DELETE FROM producto_carrito WHERE fk_carrito=?", (car['id_carrito'],))

    flash("¡Compra confirmada! (se descontó stock y se vació el carrito)", "success")
    return redirect(url_for('carrito'))

@app.get("/healthz")
def healthz():
    return "ok", 200


# =========================
# Bootstrap
# =========================
if __name__ == '__main__':
    app.run(debug=True)