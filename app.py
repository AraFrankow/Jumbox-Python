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
# Rutas base
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


# =========================
# Registro / Login / Logout
# =========================
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
# Helpers de DB / sesión
# =========================
def get_conn():
    """Conexión SQLite con row_factory y FK on."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def require_login_redirect():
    """Si no hay sesión, redirige a /login. Si hay sesión, devuelve None."""
    if 'id_cliente' not in session:
        flash("Necesitás iniciar sesión.", "error")
        return redirect(url_for('login'))
    return None

def ensure_carrito_abierto(conn, id_cliente: int):
    """Tu tabla carrito no tiene estado: 1 carrito por cliente. Si no existe, lo crea."""
    car = conn.execute(
        "SELECT * FROM carrito WHERE fk_cliente=? LIMIT 1",
        (id_cliente,)
    ).fetchone()
    if car:
        return car
    cur = conn.execute("INSERT INTO carrito(fk_cliente) VALUES (?)", (id_cliente,))
    return conn.execute("SELECT * FROM carrito WHERE id_carrito=?", (cur.lastrowid,)).fetchone()

def leer_items(conn, id_carrito: int):
    """Items del carrito + datos de producto."""
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

def listar_sucursales(conn):
    """Tu tabla sucursal no tiene nombre: generamos 'Sucursal #ID'."""
    return conn.execute("""
        SELECT id_sucursal AS id, ('Sucursal #' || id_sucursal) AS nombre
        FROM sucursal
        ORDER BY id_sucursal
    """).fetchall()

def listar_categorias(conn):
    try:
        return [r['nombre'] for r in conn.execute("SELECT nombre FROM categoria ORDER BY nombre").fetchall()]
    except sqlite3.Error:
        return []


# =========================
# Productos (listado mínimo + placeholders CRUD)
# =========================
@app.get('/productos')
def productos():
    with get_conn() as conn:
        categorias = listar_categorias(conn)
        # Alias para que tu template que usa categoria/stock_minimo/activo no rompa.
        productos = conn.execute("""
            SELECT
                id_producto AS id,
                nombre,
                precio,
                stock,                 -- lo usamos si lo querés mostrar
                NULL  AS categoria,    -- tu tabla no lo tiene como texto
                0     AS stock_minimo, -- no existe en tu schema
                1     AS activo        -- no existe en tu schema
            FROM producto
            ORDER BY id_producto
        """).fetchall()
    return render_template('vista_productos.html', productos=productos, categorias=categorias)

# Placeholders para que productos.html no tire BuildError (implementarán luego)
@app.post('/productos/crear')
def productos_crear():
    flash("Crear producto: pendiente de implementar", "error")
    return redirect(url_for('productos'))

@app.post('/productos/editar')
def productos_editar():
    flash("Editar producto: pendiente de implementar", "error")
    return redirect(url_for('productos'))

@app.post('/productos/<int:prod_id>/activar')
def productos_activar(prod_id):
    flash(f"Activar producto {prod_id}: pendiente", "error")
    return redirect(url_for('productos'))

@app.post('/productos/<int:prod_id>/desactivar')
def productos_desactivar(prod_id):
    flash(f"Desactivar producto {prod_id}: pendiente", "error")
    return redirect(url_for('productos'))


# =========================
# Carrito
# =========================
@app.get('/carrito')
def carrito():
    resp = require_login_redirect()
    if resp:
        return resp

    id_cliente = session['id_cliente']
    cliente = {"id_cliente": id_cliente, "nombre": session.get('nombre', 'Usuario')}

    with get_conn() as conn:
        # sucursales
        sucursales = listar_sucursales(conn)
        if not sucursales:
            flash("No hay sucursales cargadas.", "error")
            return redirect(url_for('home'))

        if 'sucursal_id' not in session:
            session['sucursal_id'] = sucursales[0]['id']
        sucursal_actual = next((s for s in sucursales if s['id'] == session['sucursal_id']), sucursales[0])

        # carrito + items
        car = ensure_carrito_abierto(conn, id_cliente)
        items, total = leer_items(conn, car['id_carrito'])

        categorias = listar_categorias(conn)

    return render_template(
        'vista_carrito.html',
        cliente=cliente,
        categorias=categorias,
        sucursales=sucursales,
        sucursal_actual=sucursal_actual,
        items=items,
        total=total,
        metodos_pago=['EFECTIVO', 'TARJETA']
    )

@app.post('/carrito/sucursal')
def carrito_cambiar_sucursal():
    resp = require_login_redirect()
    if resp:
        return resp
    sucursal_id = request.form.get('sucursal_id', type=int)
    if not sucursal_id:
        flash("Seleccioná una sucursal.", "error")
    else:
        session['sucursal_id'] = sucursal_id
        flash("Sucursal actualizada.", "success")
    return redirect(url_for('carrito'))

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
    observaciones = request.form.get('observaciones', '')  # hoy no se persiste

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

        # Validar stock global (tu schema)
        for it in items:
            if it['stock'] < it['cantidad']:
                flash("Stock insuficiente para uno o más productos.", "error")
                return redirect(url_for('carrito'))

        # Descontar stock y vaciar carrito (versión mínima) 
        for it in items:
            conn.execute("""
                UPDATE producto
                SET stock = stock - ?
                WHERE id_producto = ?
            """, (it['cantidad'], it['producto_id']))

        conn.execute("DELETE FROM producto_carrito WHERE fk_carrito=?", (car['id_carrito'],))

    flash("¡Compra confirmada! (se descontó stock y se vació el carrito)", "success")
    return redirect(url_for('carrito'))


# =========================
# Utilidad
# =========================
@app.get("/healthz")
def healthz():
    return "ok", 200

if __name__ == '__main__':
    app.run(debug=True)