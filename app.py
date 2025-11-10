from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import base64
from flask_bcrypt import Bcrypt
from datetime import date

# ===============================================
# CREDENCIALES DE PRUEBA
# ===============================================
# telefono admin: 12345678
# contraseña admin: Admin1234

# telefono usuario1: 87654321
# contraseña usuario1: Usuario1234

# telefono sucursal1: 09876543
# contraseña sucursal1: Sucursal1111

# telefono sucursal2: 98765432
# contraseña sucursal2: Sucursal2222

# telefono sucursal3: 76543210
# contraseña sucursal3: Sucursal3333

# ===============================================
# CONFIGURACIÓN DE LA APP
# ===============================================
app = Flask(__name__)
app.secret_key = 'clave_secreta_super_segura'
bcrypt = Bcrypt(app)
DB_NAME = "jumbox.db"

# ===== Paso 1: Config =====
# Usuario que vamos a convertir en "sucursal" y vincular a la sucursal creada/primera
USUARIO_SUCURSAL_TELEFONO = None

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

<<<<<<< HEAD
# ===============================================
# FUNCIONES AUXILIARES - BASE DE DATOS
# ===============================================
=======
# =========================
# Helpers de DB / sesión
# =========================
>>>>>>> 91421f835a6e22ee5cfaa57205abbbb59b583ef5
def get_conn():
    """Conexión SQLite con row_factory y FK on."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def require_login_redirect():
    """Si no hay sesión, redirige a /login."""
    if 'id_cliente' not in session:
        flash("Necesitás iniciar sesión.", "error")
        return redirect(url_for('login'))
    return None

def ensure_carrito_abierto(conn, id_cliente: int):
    """Obtiene o crea el carrito del cliente."""
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
    """Lista todas las sucursales (clientes tipo 'sucursal')."""
    return conn.execute("""
        SELECT id_cliente AS id, 
               nombre AS nombre,
               direccion AS direccion
        FROM cliente
        WHERE tipo = 'sucursal'
        ORDER BY id_cliente
    """).fetchall()

def listar_categorias(conn):
    """Lista todas las categorías disponibles."""
    try:
        return [r['nombre'] for r in conn.execute("SELECT nombre FROM categoria ORDER BY nombre").fetchall()]
    except sqlite3.Error:
        return []

<<<<<<< HEAD
def get_productos_sucursal(conn, cliente_sucursal_id: int):
    """Obtiene todos los productos con su stock en una sucursal específica."""
    return conn.execute("""
        SELECT 
            p.id_producto AS id,
            p.nombre,
            p.precio,
            COALESCE(a.cantidad, 0) AS stock_sucursal,
            c.nombre AS categoria
        FROM producto p
        LEFT JOIN almacen_sucursal a 
            ON a.fk_producto = p.id_producto 
            AND a.fk_sucursal = ?
        JOIN categoria c ON c.id_categoria = p.fk_categoria
        ORDER BY p.nombre
    """, (cliente_sucursal_id,)).fetchall()
=======
def get_stock_actual(conn, sucursal_id: int, producto_id: int) -> int:
    """Devuelve stock actual de un producto en una sucursal (almacen_sucursal)."""
    row = conn.execute("""
        SELECT COALESCE(a.cantidad, 0) AS cant
        FROM producto p
        LEFT JOIN almacen_sucursal a
              ON a.fk_producto = p.id_producto
             AND a.fk_sucursal = ?
        WHERE p.id_producto = ?
    """, (sucursal_id, producto_id)).fetchone()
    return row['cant'] if row else 0

def listar_solicitudes_sucursal(conn, sucursal_id: int):
    """
    Devuelve las solicitudes de reposición de una sucursal con su detalle (1 fila por producto).
    pedido_reposicion (cabecera) + detalle_pedido_reposicion (detalle) + producto (nombre)
    """
    return conn.execute("""
        SELECT
            pr.id_pedido_reposicion AS id,
            pr.fecha                 AS fecha,
            p.nombre                 AS producto,
            dpr.cantidad             AS cantidad
        FROM pedido_reposicion pr
        JOIN detalle_pedido_reposicion dpr
          ON dpr.fk_pedido_reposicion = pr.id_pedido_reposicion
        JOIN producto p
          ON p.id_producto = dpr.fk_producto
        WHERE pr.fk_sucursal = ?
        ORDER BY pr.id_pedido_reposicion DESC, dpr.id_detalle_pedido_reposicion DESC
    """, (sucursal_id,)).fetchall()

# =========================
# Paso 1 (automático, idempotente)
# =========================
def paso1_configurar_sucursal():
    """
    - Crea una sucursal si no existe ninguna.
    - Convierte al cliente con telefono USUARIO_SUCURSAL_TELEFONO en 'sucursal' y lo vincula.
    - Inicializa almacen_sucursal (stock 0) para todos los productos de esa sucursal.
    Es idempotente: si ya existe, no duplica.
    """
    try:
        with get_conn() as conn:
            # 1) Obtener/crear sucursal
            row = conn.execute("SELECT id_sucursal FROM sucursal ORDER BY id_sucursal LIMIT 1").fetchone()
            if row:
                sucursal_id = row['id_sucursal']
            else:
                cur = conn.execute("INSERT INTO sucursal (contrasena) VALUES (?)", ("suc1",))
                sucursal_id = cur.lastrowid

            # 2) Ver si existe el cliente por teléfono
            cli = conn.execute("""
                SELECT id_cliente, tipo, fk_sucursal
                FROM cliente
                WHERE telefono = ?
            """, (USUARIO_SUCURSAL_TELEFONO,)).fetchone()

            if cli:
                # Si ya está seteado, lo dejamos; si no, lo establecemos
                if cli['fk_sucursal'] != sucursal_id or cli['tipo'] != 'sucursal':
                    conn.execute("""
                        UPDATE cliente
                           SET tipo = 'sucursal',
                               fk_sucursal = ?
                         WHERE id_cliente = ?
                    """, (sucursal_id, cli['id_cliente']))
            # Si no existe ese cliente, no hacemos nada más (lo puede crear desde /registro)
            # 3) Inicializar almacen de sucursal con 0 para todos los productos (solo los que falten)
            conn.execute("""
                INSERT OR IGNORE INTO almacen_sucursal(fk_sucursal, fk_producto, cantidad)
                SELECT ?, p.id_producto, 0
                  FROM producto p
            """, (sucursal_id,))
    except Exception as e:
        # Evitamos romper la app si el ALTER TABLE aún no fue corrido
        print(f"[PASO1] Aviso: no se pudo completar configuración inicial: {e}")

# =========================
# Rutas base
# =========================
@app.route('/')
def home():
    categoria_filtro = request.args.get('categoria', None)
    conn = get_conn()

    categorias = conn.execute("SELECT nombre FROM categoria ORDER BY nombre").fetchall()
    categorias_lista = [c['nombre'] for c in categorias]

    if categoria_filtro:
        productos = conn.execute("""
            SELECT
                p.id_producto AS id,
                p.nombre,
                p.precio,
                p.stock,
                p.imagen,
                p.fk_categoria,
                c.nombre AS categoria_nombre
            FROM producto p
            JOIN categoria c ON p.fk_categoria = c.id_categoria
            WHERE c.nombre = ?
            ORDER BY p.id_producto DESC
        """, (categoria_filtro,)).fetchall()
    else:
        productos = conn.execute("""
            SELECT
                p.id_producto AS id,
                p.nombre,
                p.precio,
                p.stock,
                p.imagen,
                p.fk_categoria,
                c.nombre AS categoria_nombre
            FROM producto p
            JOIN categoria c ON p.fk_categoria = c.id_categoria
            ORDER BY p.id_producto DESC
        """).fetchall()

    productos_con_imagen = []
    for p in productos:
        producto_dict = dict(p)
        if producto_dict['imagen']:
            producto_dict['imagen_base64'] = base64.b64encode(producto_dict['imagen']).decode('utf-8')
        else:
            producto_dict['imagen_base64'] = None
        productos_con_imagen.append(producto_dict)

    conn.close()

    print(f"Total de productos: {len(productos_con_imagen)}")
    if productos_con_imagen:
        print(f"Primer producto: {productos_con_imagen[0]['nombre']}")

    return render_template('index.html',
                        productos=productos_con_imagen,
                        categorias=categorias_lista,
                        categoria_actual=categoria_filtro)

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
        cursor.execute("""
            SELECT id_cliente, nombre, contrasena, tipo, fk_sucursal
            FROM cliente
            WHERE telefono = ?
        """, (tel,))
        cliente = cursor.fetchone()
        conn.close()

        if cliente and bcrypt.check_password_hash(cliente[2], contra):
            session['id_cliente'] = cliente[0]
            session['nombre'] = cliente[1]
            session['tipo'] = cliente[3]
            if cliente[4]:
                session['sucursal_id'] = cliente[4]
            flash("Inicio de sesión exitoso", "success")
            # si es usuario de sucursal => panel de sucursal; si no, home
            return redirect(url_for('panel_sucursal' if cliente[3] == 'sucursal' else 'home'))

        flash("Credenciales incorrectas", "error")
        return render_template('login.html', tel=tel)

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada correctamente', 'success')
    return redirect(url_for('home'))

# =========================
# Sucursal
# =========================
@app.get('/sucursal')
def vista_sucursal():
    """Formulario 'Pedir Stock' y lista de solicitudes de la sucursal (sin JS)."""
    resp = require_login_redirect()
    if resp:
        return resp

    with get_conn() as conn:
        # Sucursal actual en sesión; si no hay, usamos la primera disponible
        sucursales = listar_sucursales(conn)
        if not sucursales:
            flash("No hay sucursales cargadas.", "error")
            return redirect(url_for('home'))

        if 'sucursal_id' not in session:
            session['sucursal_id'] = sucursales[0]['id']
        sucursal_id = session['sucursal_id']

        # Productos para el select
        productos = conn.execute("""
            SELECT id_producto, nombre
            FROM producto
            ORDER BY nombre
        """).fetchall()

        # Stock actual (si viene ?producto_id=... en la query)
        selected_producto_id = request.args.get('producto_id', type=int)
        stock_actual = None
        if selected_producto_id:
            stock_actual = get_stock_actual(conn, sucursal_id, selected_producto_id)

        # Solicitudes (cabecera+detalle) según tu schema
        solicitudes = listar_solicitudes_sucursal(conn, sucursal_id)

    return render_template(
        'sucursal.html',
        productos=productos,
        sucursal_id=sucursal_id,
        selected_producto_id=selected_producto_id,
        stock_actual=stock_actual,
        solicitudes=solicitudes  # si más adelante querés mostrarlas abajo
    )

@app.get('/panel-sucursal')
def panel_sucursal():
    resp = require_login_redirect()
    if resp:
        return resp
    if session.get('tipo') != 'sucursal':
        flash("No autorizado.", "error")
        return redirect(url_for('home'))
    return render_template('panel_sucursal.html', sucursal_id=session.get('sucursal_id'))

@app.get('/sucursal/pedidos-clientes')
def sucursal_pedidos_clientes():
    """Muestra los pedidos realizados por clientes, pendientes de envío."""
    resp = require_login_redirect()
    if resp:
        return resp
    if session.get('tipo') != 'sucursal':
        flash("No autorizado.", "error")
        return redirect(url_for('home'))

    with get_conn() as conn:
        pedidos = conn.execute("""
            SELECT
                ped.id_pedido,
                ped.fecha,
                ped.estado,
                cli.nombre AS cliente_nombre,
                p.nombre AS producto_nombre,
                dp.cantidad
            FROM pedido ped
            JOIN cliente cli ON cli.id_cliente = ped.fk_cliente
            JOIN detalles_pedido dp ON dp.fk_pedido = ped.id_pedido
            JOIN producto p ON p.id_producto = dp.fk_producto
            ORDER BY ped.id_pedido DESC
        """).fetchall()

    return render_template('sucursal_pedidos_clientes.html', pedidos=pedidos)

@app.post('/sucursal/pedidos-clientes/enviar/<int:id_pedido>')
def sucursal_enviar_pedido(id_pedido):
    """Marca el pedido como enviado y actualiza el stock de la sucursal."""
    resp = require_login_redirect()
    if resp:
        return resp
    if session.get('tipo') != 'sucursal':
        flash("No autorizado.", "error")
        return redirect(url_for('home'))

    sucursal_id = session.get('sucursal_id')
    if not sucursal_id:
        flash("No hay sucursal activa.", "error")
        return redirect(url_for('panel_sucursal'))

    with get_conn() as conn:
        try:
            # Obtener los productos y cantidades del pedido
            items = conn.execute("""
                SELECT fk_producto, cantidad
                FROM detalles_pedido
                WHERE fk_pedido = ?
            """, (id_pedido,)).fetchall()

            # Restar stock de la sucursal en almacen_sucursal
            for it in items:
                conn.execute("""
                    UPDATE almacen_sucursal
                    SET cantidad = cantidad - ?
                    WHERE fk_sucursal = ? AND fk_producto = ?
                """, (it['cantidad'], sucursal_id, it['fk_producto']))

            # Actualizar estado del pedido
            conn.execute("""
                UPDATE pedido
                SET estado = 'enviado'
                WHERE id_pedido = ?
            """, (id_pedido,))

            conn.commit()
            flash(f"Pedido #{id_pedido} marcado como enviado.", "success")

        except Exception as e:
            conn.rollback()
            flash(f"Error al actualizar el pedido: {e}", "error")

    return redirect(url_for('sucursal_pedidos_clientes'))



>>>>>>> 91421f835a6e22ee5cfaa57205abbbb59b583ef5

# ===============================================
# RUTAS PRINCIPALES
# ===============================================
@app.route('/')
def home():
    categoria_filtro = request.args.get('categoria', None)
    conn = get_conn()

    # Obtener sucursales para el selector
    sucursales = listar_sucursales(conn)
    
    # Sucursal seleccionada (de sesión o primera disponible)
    if 'cliente_sucursal_id' not in session and sucursales:
        session['cliente_sucursal_id'] = sucursales[0]['id']
    
    cliente_sucursal_id = session.get('cliente_sucursal_id')

    categorias = conn.execute("SELECT nombre FROM categoria ORDER BY nombre").fetchall()
    categorias_lista = [c['nombre'] for c in categorias]

    # Consultar productos con stock de la sucursal seleccionada
    if categoria_filtro:
        productos = conn.execute("""
            SELECT
<<<<<<< HEAD
                p.id_producto AS id,
                p.nombre,
                p.precio,
                COALESCE(a.cantidad, 0) AS stock,
                p.imagen,
                p.fk_categoria,
                c.nombre AS categoria_nombre
            FROM producto p
            JOIN categoria c ON p.fk_categoria = c.id_categoria
            LEFT JOIN almacen_sucursal a 
                ON a.fk_producto = p.id_producto 
                AND a.fk_sucursal = ?
            WHERE c.nombre = ?
            ORDER BY p.id_producto DESC
        """, (cliente_sucursal_id, categoria_filtro)).fetchall()
    else:
        productos = conn.execute("""
            SELECT
                p.id_producto AS id,
                p.nombre,
                p.precio,
                COALESCE(a.cantidad, 0) AS stock,
                p.imagen,
                p.fk_categoria,
                c.nombre AS categoria_nombre
            FROM producto p
            JOIN categoria c ON p.fk_categoria = c.id_categoria
            LEFT JOIN almacen_sucursal a 
                ON a.fk_producto = p.id_producto 
                AND a.fk_sucursal = ?
            ORDER BY p.id_producto DESC
        """, (cliente_sucursal_id,)).fetchall()

    productos_con_imagen = []
    for p in productos:
        producto_dict = dict(p)
        if producto_dict['imagen']:
            producto_dict['imagen_base64'] = base64.b64encode(producto_dict['imagen']).decode('utf-8')
        else:
            producto_dict['imagen_base64'] = None
        productos_con_imagen.append(producto_dict)

    conn.close()
=======
                id_producto AS id,
                nombre,
                precio,
                stock,
                NULL  AS categoria,
                0     AS stock_minimo,
                1     AS activo
            FROM producto
            ORDER BY id_producto
        """).fetchall()
    return render_template('vista_productos.html', productos=productos, categorias=categorias)

@app.post('/productos/editar')
def productos_editar():
    flash("Editar producto: pendiente de implementar", "error")
    return redirect(url_for('productos'))
>>>>>>> 91421f835a6e22ee5cfaa57205abbbb59b583ef5

    return render_template('index.html',
                        productos=productos_con_imagen,
                        categorias=categorias_lista,
                        categoria_actual=categoria_filtro,
                        sucursales=sucursales,
                        cliente_sucursal_id=cliente_sucursal_id)

@app.route('/cambiar-sucursal', methods=['POST'])
def cambiar_sucursal():
    """Cambiar la sucursal seleccionada en el index."""
    cliente_sucursal_id = request.form.get('cliente_sucursal_id', type=int)
    if not cliente_sucursal_id:
        flash("Selecciona una sucursal válida.", "error")
    else:
        session['cliente_sucursal_id'] = cliente_sucursal_id
        flash("Sucursal cambiada correctamente.", "success")
    return redirect(url_for('home'))

<<<<<<< HEAD
@app.errorhandler(404)
def pagina_no_encontrada(e):
    return render_template('404.html'), 404

@app.errorhandler(405)
def pagina_no_encontrada2(e):
    return render_template('404.html'), 405

# ===============================================
# AUTENTICACIÓN
# ===============================================
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
            return redirect(url_for('login'))
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
            
            # Redirigir según tipo de usuario
            if cliente[3] == 'sucursal':
                return redirect(url_for('panel_sucursal'))
            elif cliente[3] == 'admin':
                return redirect(url_for('admin'))
            else:
                return redirect(url_for('home'))

        flash("Credenciales incorrectas", "error")
        return render_template('login.html', tel=tel)

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada correctamente', 'success')
    return redirect(url_for('home'))

# ===============================================
# CARRITO
# ===============================================
=======
# =========================
# Carrito
# =========================
>>>>>>> 91421f835a6e22ee5cfaa57205abbbb59b583ef5
@app.get('/carrito')
def carrito():
    resp = require_login_redirect()
    if resp:
        return resp

    id_cliente = session['id_cliente']
    cliente = {"id_cliente": id_cliente, "nombre": session.get('nombre', 'Usuario')}

    with get_conn() as conn:
        sucursales = listar_sucursales(conn)
        if not sucursales:
            flash("No hay sucursales cargadas.", "error")
            return redirect(url_for('home'))

        if 'cliente_sucursal_id' not in session:
            session['cliente_sucursal_id'] = sucursales[0]['id']
        
        sucursal_actual = next((s for s in sucursales if s['id'] == session['cliente_sucursal_id']), sucursales[0])

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

    metodo_pago = request.form.get('metodo_pago')

    if metodo_pago not in ('EFECTIVO', 'TARJETA'):
        flash("Seleccioná un método de pago válido.", "error")
        return redirect(url_for('carrito'))

    id_cliente = session['id_cliente']
    cliente_sucursal_id = session.get('cliente_sucursal_id')

    with get_conn() as conn:
        car = ensure_carrito_abierto(conn, id_cliente)

        items = conn.execute("""
            SELECT pc.fk_producto AS producto_id, pc.cantidad, 
                p.precio, 
                COALESCE(a.cantidad, 0) AS stock_sucursal
            FROM producto_carrito pc
            JOIN producto p ON p.id_producto = pc.fk_producto
            LEFT JOIN almacen_sucursal a 
                ON a.fk_producto = pc.fk_producto 
                AND a.fk_sucursal = ?
            WHERE pc.fk_carrito=?
        """, (cliente_sucursal_id, car['id_carrito'])).fetchall()

        if not items:
            flash("Tu carrito está vacío.", "error")
            return redirect(url_for('carrito'))

        # Validar stock de la sucursal
        for it in items:
            if it['stock_sucursal'] < it['cantidad']:
                flash(f"Stock insuficiente en la sucursal para uno o más productos.", "error")
                return redirect(url_for('carrito'))

<<<<<<< HEAD
        # Crear pedido
        cursor = conn.execute("""
            INSERT INTO pedido (fecha, estado, fk_cliente, fk_sucursal)
            VALUES (?, 'pendiente', ?, ?)
        """, (date.today().isoformat(), id_cliente, cliente_sucursal_id))
        
        pedido_id = cursor.lastrowid

        # Agregar detalles y descontar stock
=======
        # Descontar stock y vaciar carrito (versión mínima)
>>>>>>> 91421f835a6e22ee5cfaa57205abbbb59b583ef5
        for it in items:
            conn.execute("""
                INSERT INTO detalles_pedido (cantidad, fk_producto, fk_pedido)
                VALUES (?, ?, ?)
            """, (it['cantidad'], it['producto_id'], pedido_id))
            
            # Descontar del almacén de la sucursal
            conn.execute("""
                UPDATE almacen_sucursal
                SET cantidad = cantidad - ?
                WHERE fk_sucursal = ? AND fk_producto = ?
            """, (it['cantidad'], cliente_sucursal_id, it['producto_id']))

        # Vaciar carrito
        conn.execute("DELETE FROM producto_carrito WHERE fk_carrito=?", (car['id_carrito'],))

    flash("¡Compra confirmada!", "success")
    return redirect(url_for('home'))

<<<<<<< HEAD
# ===============================================
# PANEL SUCURSAL
# ===============================================
@app.get('/panel-sucursal')
def panel_sucursal():
    resp = require_login_redirect()
    if resp:
        return resp
    if session.get('tipo') != 'sucursal':
        flash("No autorizado.", "error")
        return redirect(url_for('home'))
    return render_template('panel_sucursal.html')

@app.route('/sucursal/almacen')
def sucursal_almacen():
    """Ver el almacén de la sucursal con stock de productos."""
    resp = require_login_redirect()
    if resp:
        return resp
    
    if session.get('tipo') != 'sucursal':
        flash("No autorizado.", "error")
        return redirect(url_for('home'))
    
    cliente_sucursal_id = session.get('id_cliente')
    
    with get_conn() as conn:
        sucursal = conn.execute("""
            SELECT nombre AS nombre, direccion AS direccion 
            FROM cliente 
            WHERE id_cliente = ?
        """, (cliente_sucursal_id,)).fetchone()
        
        productos = get_productos_sucursal(conn, cliente_sucursal_id)
    
    return render_template('sucursal_almacen.html', 
                         sucursal=sucursal, 
                         productos=productos)

@app.route('/sucursal/pedir-stock', methods=['GET', 'POST'])
def sucursal_pedir_stock():
    """Formulario para pedir reposición de stock."""
    resp = require_login_redirect()
    if resp:
        return resp
    
    if session.get('tipo') != 'sucursal':
        flash("No autorizado.", "error")
        return redirect(url_for('home'))
    
    cliente_sucursal_id = session.get('id_cliente')
    
    if request.method == 'POST':
        producto_id = request.form.get('producto_id', type=int)
        cantidad = request.form.get('cantidad', type=int)
        
        if not producto_id or not cantidad or cantidad < 1:
            flash("Datos inválidos.", "error")
            return redirect(url_for('sucursal_pedir_stock'))
        
        with get_conn() as conn:
            try:
                cursor = conn.execute("""
                    INSERT INTO pedido_reposicion (fecha, fk_sucursal)
                    VALUES (?, ?)
                """, (date.today().isoformat(), cliente_sucursal_id))
                
                pedido_id = cursor.lastrowid
                
                conn.execute("""
                    INSERT INTO detalle_pedido_reposicion 
                    (cantidad, fk_pedido_reposicion, fk_producto)
                    VALUES (?, ?, ?)
                """, (cantidad, pedido_id, producto_id))
                
                conn.commit()
                flash("Solicitud de stock enviada correctamente.", "success")
                return redirect(url_for('sucursal_pedir_stock'))
                
            except Exception as e:
                conn.rollback()
                flash(f"Error al crear solicitud: {e}", "error")
    
    # GET - Obtener datos para el formulario
    with get_conn() as conn:
        # Obtener nombre de la sucursal
        sucursal = conn.execute("""
            SELECT nombre FROM cliente WHERE id_cliente = ?
        """, (cliente_sucursal_id,)).fetchone()
        
        sucursal_nombre = sucursal['nombre'] if sucursal else "Sucursal"
        
        # Obtener productos con su stock actual en esta sucursal
        productos = conn.execute("""
            SELECT 
                p.id_producto,
                p.nombre,
                COALESCE(a.cantidad, 0) AS stock_actual
            FROM producto p
            LEFT JOIN almacen_sucursal a 
                ON a.fk_producto = p.id_producto 
                AND a.fk_sucursal = ?
            ORDER BY p.nombre
        """, (cliente_sucursal_id,)).fetchall()
    
    return render_template('sucursal_pedir_stock.html', 
                        productos=productos,
                        sucursal_nombre=sucursal_nombre)

@app.get('/sucursal/pedidos-clientes')
def sucursal_pedidos_clientes():
    """Muestra los pedidos realizados por clientes."""
    resp = require_login_redirect()
    if resp:
        return resp
    if session.get('tipo') != 'sucursal':
        flash("No autorizado.", "error")
        return redirect(url_for('home'))

    cliente_sucursal_id = session.get('id_cliente')

    with get_conn() as conn:
        pedidos = conn.execute("""
            SELECT
                ped.id_pedido,
                ped.fecha,
                ped.estado,
                cli.nombre AS cliente_nombre,
                p.nombre AS producto_nombre,
                dp.cantidad
            FROM pedido ped
            JOIN cliente cli ON cli.id_cliente = ped.fk_cliente
            JOIN detalles_pedido dp ON dp.fk_pedido = ped.id_pedido
            JOIN producto p ON p.id_producto = dp.fk_producto
            WHERE ped.fk_sucursal = ?
            ORDER BY ped.id_pedido DESC
        """, (cliente_sucursal_id,)).fetchall()

    return render_template('sucursal_pedidos_clientes.html', pedidos=pedidos)

@app.post('/sucursal/pedidos-clientes/enviar/<int:id_pedido>')
def sucursal_enviar_pedido(id_pedido):
    """Marca el pedido como enviado."""
    resp = require_login_redirect()
    if resp:
        return resp
    if session.get('tipo') != 'sucursal':
        flash("No autorizado.", "error")
        return redirect(url_for('home'))

    with get_conn() as conn:
        try:
            conn.execute("""
                UPDATE pedido
                SET estado = 'enviado'
                WHERE id_pedido = ?
            """, (id_pedido,))

            conn.commit()
            flash(f"Pedido #{id_pedido} marcado como enviado.", "success")

        except Exception as e:
            conn.rollback()
            flash(f"Error al actualizar el pedido: {e}", "error")

    return redirect(url_for('sucursal_pedidos_clientes'))

# ===============================================
# PANEL ADMIN
# ===============================================
=======
# =========================
# Admin
# =========================
>>>>>>> 91421f835a6e22ee5cfaa57205abbbb59b583ef5
@app.route('/administracion')
def admin():
    resp = require_login_redirect()
    if resp:
        return resp
    if session.get('tipo') != 'admin':
        flash("No autorizado.", "error")
        return redirect(url_for('home'))
    return render_template('admin.html')

@app.route('/admin/solicitudes')
def admin_solicitudes():
    """Ver todas las solicitudes de reposición."""
    resp = require_login_redirect()
    if resp:
        return resp
    
    if session.get('tipo') != 'admin':
        flash("No autorizado.", "error")
        return redirect(url_for('home'))
    
    with get_conn() as conn:
        solicitudes = conn.execute("""
            SELECT 
                pr.id_pedido_reposicion AS id,
                pr.fecha,
                c.nombre AS sucursal,
                p.nombre AS producto,
                dpr.cantidad,
                pr.fk_sucursal AS sucursal_id,
                dpr.fk_producto AS producto_id
            FROM pedido_reposicion pr
            JOIN cliente c ON c.id_cliente = pr.fk_sucursal
            JOIN detalle_pedido_reposicion dpr 
                ON dpr.fk_pedido_reposicion = pr.id_pedido_reposicion
            JOIN producto p ON p.id_producto = dpr.fk_producto
            ORDER BY pr.id_pedido_reposicion DESC
        """).fetchall()
    
    return render_template('admin_solicitudes.html', solicitudes=solicitudes)

@app.route('/admin/solicitudes/aprobar/<int:solicitud_id>', methods=['POST'])
def admin_aprobar_solicitud(solicitud_id):
    """Aprobar una solicitud y transferir stock a la sucursal."""
    resp = require_login_redirect()
    if resp:
        return resp
    
    if session.get('tipo') != 'admin':
        flash("No autorizado.", "error")
        return redirect(url_for('home'))
    
    with get_conn() as conn:
        try:
            solicitud = conn.execute("""
                SELECT 
                    pr.fk_sucursal,
                    dpr.fk_producto,
                    dpr.cantidad
                FROM pedido_reposicion pr
                JOIN detalle_pedido_reposicion dpr 
                    ON dpr.fk_pedido_reposicion = pr.id_pedido_reposicion
                WHERE pr.id_pedido_reposicion = ?
            """, (solicitud_id,)).fetchone()
            
            if not solicitud:
                flash("Solicitud no encontrada.", "error")
                return redirect(url_for('admin_solicitudes'))
            
            cliente_sucursal_id = solicitud['fk_sucursal']
            producto_id = solicitud['fk_producto']
            cantidad = solicitud['cantidad']
            
            stock_global = conn.execute("""
                SELECT stock FROM producto WHERE id_producto = ?
            """, (producto_id,)).fetchone()
            
            if not stock_global or stock_global['stock'] < cantidad:
                flash("No hay suficiente stock global.", "error")
                return redirect(url_for('admin_solicitudes'))
            
            # Restar del stock global
            conn.execute("""
                UPDATE producto 
                SET stock = stock - ? 
                WHERE id_producto = ?
            """, (cantidad, producto_id))
            
            # Sumar al almacén de la sucursal
            conn.execute("""
                INSERT INTO almacen_sucursal (fk_sucursal, fk_producto, cantidad)
                VALUES (?, ?, ?)
                ON CONFLICT(fk_sucursal, fk_producto) 
                DO UPDATE SET cantidad = cantidad + ?
            """, (cliente_sucursal_id, producto_id, cantidad, cantidad))
            
            # Eliminar la solicitud
            conn.execute("""
                DELETE FROM detalle_pedido_reposicion 
                WHERE fk_pedido_reposicion = ?
            """, (solicitud_id,))
            
            conn.execute("""
                DELETE FROM pedido_reposicion 
                WHERE id_pedido_reposicion = ?
            """, (solicitud_id,))
            
            conn.commit()
            flash("Solicitud aprobada y stock transferido.", "success")
            
        except Exception as e:
            conn.rollback()
            flash(f"Error al aprobar solicitud: {e}", "error")
    
    return redirect(url_for('admin_solicitudes'))

@app.route('/admin/solicitudes/rechazar/<int:solicitud_id>', methods=['POST'])
def admin_rechazar_solicitud(solicitud_id):
    """Rechazar y eliminar una solicitud."""
    resp = require_login_redirect()
    if resp:
        return resp
    
    if session.get('tipo') != 'admin':
        flash("No autorizado.", "error")
        return redirect(url_for('home'))
    
    with get_conn() as conn:
        try:
            conn.execute("""
                DELETE FROM detalle_pedido_reposicion 
                WHERE fk_pedido_reposicion = ?
            """, (solicitud_id,))
            
            conn.execute("""
                DELETE FROM pedido_reposicion 
                WHERE id_pedido_reposicion = ?
            """, (solicitud_id,))
            
            conn.commit()
            flash("Solicitud rechazada.", "success")
            
        except Exception as e:
            conn.rollback()
            flash(f"Error al rechazar solicitud: {e}", "error")
    
    return redirect(url_for('admin_solicitudes'))

# ===============================================
# GESTIÓN DE PRODUCTOS (ADMIN)
# ===============================================
@app.route('/crear-producto', methods=['GET', 'POST'])
def crear_producto():
    resp = require_login_redirect()
    if resp:
        return resp

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        precio = request.form.get('precio')
        stock = request.form.get('stock')
        categoria = request.form.get('categoria')

<<<<<<< HEAD
=======
        # Validaciones básicas
>>>>>>> 91421f835a6e22ee5cfaa57205abbbb59b583ef5
        if not nombre or not precio or not stock or not categoria:
            flash('Todos los campos son obligatorios', 'error')
            return redirect(url_for('crear_producto'))

        try:
            precio = float(precio)
            stock = int(stock)
        except ValueError:
            flash('Precio y stock deben ser números válidos', 'error')
            return redirect(url_for('crear_producto'))

<<<<<<< HEAD
=======
        # Manejo de la imagen
>>>>>>> 91421f835a6e22ee5cfaa57205abbbb59b583ef5
        imagen_data = None
        if 'imagen' in request.files:
            file = request.files['imagen']
            if file and file.filename != '':
                if allowed_file(file.filename):
                    imagen_data = file.read()
                else:
                    flash('Formato de imagen no permitido', 'error')
                    return redirect(url_for('crear_producto'))

<<<<<<< HEAD
=======
        # Obtener el id de la categoría
>>>>>>> 91421f835a6e22ee5cfaa57205abbbb59b583ef5
        with get_conn() as conn:
            cat_row = conn.execute("SELECT id_categoria FROM categoria WHERE nombre = ?", (categoria,)).fetchone()
            if not cat_row:
                flash('Categoría no válida', 'error')
                return redirect(url_for('crear_producto'))

            fk_categoria = cat_row['id_categoria']

<<<<<<< HEAD
=======
            # Insertar el producto
>>>>>>> 91421f835a6e22ee5cfaa57205abbbb59b583ef5
            conn.execute("""
                INSERT INTO producto (nombre, precio, stock, fk_categoria, imagen)
                VALUES (?, ?, ?, ?, ?)
            """, (nombre, precio, stock, fk_categoria, imagen_data))
            conn.commit()

        flash('Producto creado exitosamente', 'success')
        return redirect(url_for('home'))

<<<<<<< HEAD
=======
    # GET - Mostrar el formulario
>>>>>>> 91421f835a6e22ee5cfaa57205abbbb59b583ef5
    with get_conn() as conn:
        categorias = listar_categorias(conn)

    return render_template('crear_producto.html', categorias=categorias)

@app.route('/editar-productos')
def listar_productos_para_editar():
    resp = require_login_redirect()
    if resp:
        return resp
    
    with get_conn() as conn:
        productos = conn.execute("SELECT id_producto, nombre, precio, stock FROM producto").fetchall()
    return render_template('listar_productos.html', productos=productos)

@app.route('/editar-producto/<int:id_producto>', methods=['GET', 'POST'])
def editar_producto(id_producto):
    resp = require_login_redirect()
    if resp:
        return resp
<<<<<<< HEAD
=======

    with get_conn() as conn:
        # Obtener categorías (para el select)
        categorias = listar_categorias(conn)
>>>>>>> 91421f835a6e22ee5cfaa57205abbbb59b583ef5

    with get_conn() as conn:
        categorias = listar_categorias(conn)
        
        producto = conn.execute("""
            SELECT p.id_producto, p.nombre, p.precio, p.stock, c.nombre AS categoria
            FROM producto p
            JOIN categoria c ON p.fk_categoria = c.id_categoria
            WHERE p.id_producto = ?
        """, (id_producto,)).fetchone()

        if not producto:
            flash('Producto no encontrado', 'error')
            return redirect(url_for('home'))

<<<<<<< HEAD
=======
    # --- POST: actualizar el producto ---
>>>>>>> 91421f835a6e22ee5cfaa57205abbbb59b583ef5
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        precio = request.form.get('precio')
        stock = request.form.get('stock')
        categoria = request.form.get('categoria')

        if not nombre or not precio or not stock or not categoria:
            flash('Todos los campos son obligatorios', 'error')
            return redirect(url_for('editar_producto', id_producto=id_producto))

        try:
            precio = float(precio)
            stock = int(stock)
        except ValueError:
            flash('Precio y stock deben ser números válidos', 'error')
            return redirect(url_for('editar_producto', id_producto=id_producto))

        imagen_data = None
        if 'imagen' in request.files:
            file = request.files['imagen']
            if file and file.filename != '':
                if allowed_file(file.filename):
                    imagen_data = file.read()
                else:
                    flash('Formato de imagen no permitido', 'error')
                    return redirect(url_for('editar_producto', id_producto=id_producto))

        with get_conn() as conn:
            cat_row = conn.execute("SELECT id_categoria FROM categoria WHERE nombre = ?", (categoria,)).fetchone()
            if not cat_row:
                flash('Categoría no válida', 'error')
                return redirect(url_for('editar_producto', id_producto=id_producto))

            fk_categoria = cat_row['id_categoria']

            if imagen_data:
                conn.execute("""
                    UPDATE producto
                    SET nombre = ?, precio = ?, stock = ?, fk_categoria = ?, imagen = ?
                    WHERE id_producto = ?
                """, (nombre, precio, stock, fk_categoria, imagen_data, id_producto))
            else:
                conn.execute("""
                    UPDATE producto
                    SET nombre = ?, precio = ?, stock = ?, fk_categoria = ?
                    WHERE id_producto = ?
                """, (nombre, precio, stock, fk_categoria, id_producto))

            conn.commit()

        flash('Producto actualizado correctamente', 'success')
        return redirect(url_for('home'))

    return render_template('editar_producto.html', categorias=categorias, producto=producto)

<<<<<<< HEAD
# ===============================================
# PRODUCTOS (VISTA GENERAL)
# ===============================================
@app.get('/productos')
def productos():
    with get_conn() as conn:
        categorias = listar_categorias(conn)
        productos = conn.execute("""
            SELECT
                id_producto AS id,
                nombre,
                precio,
                stock,
                NULL  AS categoria,
                0     AS stock_minimo,
                1     AS activo
            FROM producto
            ORDER BY id_producto
        """).fetchall()
    return render_template('vista_productos.html', productos=productos, categorias=categorias)

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

# ===============================================
# INICIALIZACIÓN
# ===============================================
def inicializar_base_datos():
    """Inicializa datos básicos si no existen."""
    try:
        with get_conn() as conn:
            # Verificar si existen sucursales (clientes tipo 'sucursal')
            cursor = conn.execute("SELECT COUNT(*) as count FROM cliente WHERE tipo = 'sucursal'")
            count = cursor.fetchone()['count']
            
            if count == 0:
                print("📦 Creando sucursales de ejemplo...")
                sucursales_ejemplo = [
                    ('Sucursal Centro', 'Av. 18 de Julio 1234, Montevideo', '09876543', 'Sucursal1111'),
                    ('Sucursal Pocitos', 'Av. Brasil 2845, Montevideo', '98765432', 'Sucursal2222'),
                    ('Sucursal Carrasco', 'Av. Arocena 1567, Montevideo', '76543210', 'Sucursal3333')
                ]
                
                for nombre_suc, direccion_suc, telefono, password in sucursales_ejemplo:
                    hash_pass = bcrypt.generate_password_hash(password).decode('utf-8')
                    cursor = conn.execute("""
                        INSERT INTO cliente (nombre, direccion, telefono, contrasena, tipo)
                        VALUES (?, ?, ?, ?, 'sucursal')
                    """, (nombre_suc, direccion_suc, telefono, hash_pass))
                    
                    # Inicializar almacén de cada sucursal con todos los productos en 0
                    sucursal_id = cursor.lastrowid
                    conn.execute("""
                        INSERT INTO almacen_sucursal (fk_sucursal, fk_producto, cantidad)
                        SELECT ?, id_producto, 0
                        FROM producto
                    """, (sucursal_id,))
                
                conn.commit()
                print(f"✅ {len(sucursales_ejemplo)} sucursales creadas")
            
            # Verificar si existe admin
            cursor = conn.execute("SELECT COUNT(*) as count FROM cliente WHERE tipo = 'admin'")
            count = cursor.fetchone()['count']
            
            if count == 0:
                print("👤 Creando usuario admin de ejemplo...")
                hash_pass = bcrypt.generate_password_hash('Admin1234').decode('utf-8')
                conn.execute("""
                    INSERT INTO cliente (nombre, direccion, telefono, contrasena, tipo)
                    VALUES ('Admin', 'Av. Admin', '12345678', ?, 'admin')
                """, (hash_pass,))
                conn.commit()
                print("✅ Usuario admin creado")
            
            # Verificar si existe usuario normal
            cursor = conn.execute("SELECT COUNT(*) as count FROM cliente WHERE tipo = 'usuario'")
            count = cursor.fetchone()['count']
            
            if count == 0:
                print("👤 Creando usuario normal de ejemplo...")
                hash_pass = bcrypt.generate_password_hash('Usuario1234').decode('utf-8')
                conn.execute("""
                    INSERT INTO cliente (nombre, direccion, telefono, contrasena, tipo)
                    VALUES ('Juan', 'Av. Usuario', '87654321', ?, 'usuario')
                """, (hash_pass,))
                conn.commit()
                print("✅ Usuario normal creado")
                
    except Exception as e:
        print(f"⚠️ Error al inicializar base de datos: {e}")

# ===============================================
# MAIN
# ===============================================
if __name__ == '__main__':
    inicializar_base_datos()
    app.run(debug=True)
=======
# =========================
# MAIN
# =========================
if __name__ == '__main__':
    # Ejecutamos Paso 1 en arranque (idempotente)
    paso1_configurar_sucursal()
    app.run(debug=True)
>>>>>>> 91421f835a6e22ee5cfaa57205abbbb59b583ef5
