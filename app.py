from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import sqlite3
import os

DB_NAME = "monopoly.db"

def init_db():
    """Crea las tablas e inserta jugadores de prueba si no existen."""
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jugadores (
            id TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            saldo INTEGER NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transacciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emisor_id TEXT,
            receptor_id TEXT,
            monto INTEGER,
            concepto TEXT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insertar jugadores de prueba si la tabla está vacía
    cursor.execute("SELECT COUNT(*) FROM jugadores")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO jugadores (id, nombre, saldo) VALUES ('bank', 'ChickenBank', 50000)")
        cursor.execute("INSERT INTO jugadores (id, nombre, saldo) VALUES ('p1', 'Krlos', 1500)")
        cursor.execute("INSERT INTO jugadores (id, nombre, saldo) VALUES ('p2', 'Alonso', 1500)")
        cursor.execute("INSERT INTO jugadores (id, nombre, saldo) VALUES ('p3', 'Karla', 1500)")
        cursor.execute("INSERT INTO jugadores (id, nombre, saldo) VALUES ('p4', 'Gladys', 1500)")
        cursor.execute("INSERT INTO jugadores (id, nombre, saldo) VALUES ('p5', 'Player 5', 1500)")
        cursor.execute("INSERT INTO jugadores (id, nombre, saldo) VALUES ('p6', 'Playar 6', 1500)")
        print("Jugadores de prueba creados: p1 (Krlos), p2 (Banquero).")
        
    conexion.commit()
    conexion.close()

if not os.path.exists(DB_NAME):
    init_db()

app = FastAPI(title="Motor ChickenBank")

app.mount("/static", StaticFiles(directory="static"), name="static")



from fastapi import WebSocket, WebSocketDisconnect
from typing import List

# Gestor de conexiones activas
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

@app.websocket("/ws/{jugador_id}")
async def websocket_endpoint(websocket: WebSocket, jugador_id: str):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text() # Mantiene la conexión abierta
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# En tu ruta /api/cobrar, después de hacer el commit, agregamos:
# await manager.broadcast("update")

# --- RUTA PARA SERVIR LA APP WEB ---
@app.get("/")
def index():
    """Sirve el archivo index.html directamente al ingresar a la raíz"""
    return FileResponse("index.html")

# --- API ENDPOINTS (Datos para el JavaScript) ---

@app.post("/api/reiniciar_juego")
def reiniciar_juego():
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    
    try:
        # 1. Borrar todas las transacciones
        cursor.execute("DELETE FROM transacciones")
        cursor.execute("DELETE FROM jugadores")
        
        # 2. Resetear todos los saldos a 1500 (o el valor inicial que prefieras)
       #cursor.execute("UPDATE jugadores SET saldo = 1500")
        cursor.execute("INSERT INTO jugadores (id, nombre, saldo) VALUES ('bank', 'ChickenBank', 50000)")
        cursor.execute("INSERT INTO jugadores (id, nombre, saldo) VALUES ('p1', 'Krlos', 1500)")
        cursor.execute("INSERT INTO jugadores (id, nombre, saldo) VALUES ('p2', 'Alonso', 1500)")
        cursor.execute("INSERT INTO jugadores (id, nombre, saldo) VALUES ('p3', 'Karla', 1500)")
        cursor.execute("INSERT INTO jugadores (id, nombre, saldo) VALUES ('p4', 'Gladys', 1500)")
        cursor.execute("INSERT INTO jugadores (id, nombre, saldo) VALUES ('p5', 'Player 5', 1500)")
        cursor.execute("INSERT INTO jugadores (id, nombre, saldo) VALUES ('p6', 'Playar 6', 1500)")
        conexion.commit()

        return {"status": "success", "message": "Juego reiniciado"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        conexion.close()

@app.get("/api/jugadores")
def obtener_jugadores():
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    cursor.execute("SELECT id, nombre, saldo FROM jugadores")
    jugadores = [{"id": row[0], "nombre": row[1], "saldo": row[2]} for row in cursor.fetchall()]
    conexion.close()
    return jugadores

@app.get("/api/jugadores/{jugador_id}")
def obtener_jugador_por_id(jugador_id: str):
    """Busca un jugador específico en la base de datos"""
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    cursor.execute("SELECT id, nombre, saldo FROM jugadores WHERE id = ?", (jugador_id,))
    row = cursor.fetchone()
    conexion.close()
    
    if row is None:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
        
    return {"id": row[0], "nombre": row[1], "saldo": row[2]}

@app.get("/api/todos_jugadores")
def obtener_todos_jugadores():
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    # Excluimos al propio jugador si quieres (opcional)
    cursor.execute("SELECT id, nombre FROM jugadores")
    jugadores = [{"id": row[0], "nombre": row[1]} for row in cursor.fetchall()]
    conexion.close()
    return jugadores

from pydantic import BaseModel

# Modelo para los datos que vienen del celular
class Transaccion(BaseModel):
    emisor_id: str
    receptor_id: str
    monto: int


@app.post("/api/cobrar")
async def realizar_cobro(transaccion: Transaccion):
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    
    try:
        # 1. Actualizar saldos
        cursor.execute("UPDATE jugadores SET saldo = saldo - ? WHERE id = ?", (transaccion.monto, transaccion.emisor_id))
        cursor.execute("UPDATE jugadores SET saldo = saldo + ? WHERE id = ?", (transaccion.monto, transaccion.receptor_id))
        
        # 2. INSERTAR SOLO UNA VEZ. 
        # El concepto lo definiremos dinámicamente al leerlo, no al guardarlo.
        cursor.execute("INSERT INTO transacciones (emisor_id, receptor_id, monto, concepto) VALUES (?, ?, ?, ?)", 
                       (transaccion.emisor_id, transaccion.receptor_id, transaccion.monto, "Transacción"))
        
        conexion.commit()
        await manager.broadcast("update")

        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        conexion.close()


@app.get("/api/transacciones/{jugador_id}")
def obtener_movimientos(jugador_id: str):
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    
    # Esta consulta es mucho más eficiente y evita duplicados
    cursor.execute("""
        SELECT 
            CASE 
                WHEN emisor_id = ? THEN 'Pago a ' || r.nombre
                WHEN receptor_id = ? THEN 'Cobro de ' || e.nombre
            END as concepto,
            CASE 
                WHEN emisor_id = ? THEN -monto
                WHEN receptor_id = ? THEN monto
            END as monto_final
        FROM transacciones t
        JOIN jugadores e ON t.emisor_id = e.id
        JOIN jugadores r ON t.receptor_id = r.id
        WHERE emisor_id = ? OR receptor_id = ?
        ORDER BY fecha DESC LIMIT 7
    """, (jugador_id, jugador_id, jugador_id, jugador_id, jugador_id, jugador_id))
    
    movs = [{"concepto": row[0], "monto": row[1]} for row in cursor.fetchall()]
    conexion.close()
    return movs

