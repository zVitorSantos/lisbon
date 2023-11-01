from flask import render_template, request, Blueprint
from flask import redirect, url_for
from math import ceil
import random
import sqlite3

bp = Blueprint('routes', __name__)

@bp.route('/', methods=['GET', 'POST']) 
def index():

    nome_empresa = request.args.get('nome_empresa', '')
    nif = request.args.get('nif', '')
    
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    base_query = """
        SELECT * FROM DadosEmpresa
        WHERE (AcercaDaEmpresa != 'Informação não encontrada' AND CAE != 'Informação não encontrada') 
        AND CAST(REPLACE(REPLACE(CapitalSocial, '.', ''), ',', '.') AS REAL) >= 1000
    """

    params = []

    if nome_empresa:
        base_query += " AND Designacao LIKE ? "
        params.append(f"%{nome_empresa}%")

    if nif:
        base_query += " AND NIF = ? "
        params.append(nif)

    cur.execute(base_query, params)
    empresas = cur.fetchall()
    empresas_random = random.sample(empresas, min(len(empresas), 4))  
    conn.close()

    return render_template('index.html', empresas=empresas_random)

@bp.route('/s', methods=['GET'])
def search():
    page_str = request.args.get('page', '1')
    if not page_str.isdigit():
        page = 1
    else:
        page = int(page_str)

    per_page = 15 
    query = request.args.get('query', '').strip()
    nome_empresa = request.args.get('nome_empresa', '').strip()
    nif = request.args.get('nif', '').strip()
    regiao = request.args.get('regiao', '').strip()  

    if not any([query, nome_empresa, nif, regiao]):  
        return redirect(url_for('routes.index'))
    
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    cur.execute("SELECT DISTINCT Morada FROM DadosEmpresa")
    regioes = [row[0] for row in cur.fetchall()]

    query_conditions = "WHERE 1=1 "
    params = []

    if regiao:
        query_conditions += "AND Morada LIKE ? "
        params.append(f"%{regiao}%")

    if query.isdigit():
        query_conditions += "AND NIF = ? "
        params.append(query)
    elif query:
        query_conditions += "AND (Designacao LIKE ? OR AcercaDaEmpresa LIKE ?) "
        params.extend([f"%{query}%", f"%{query}%"])

    # Contar o número total de resultados
    cur.execute(f"SELECT COUNT(*) FROM DadosEmpresa {query_conditions}", params)
    total_results = cur.fetchone()[0]

    # Calcular o número de páginas
    total_pages = ceil(total_results / per_page)
    
    # Modificar a consulta SQL para incluir LIMIT e OFFSET
    query_sql = f"SELECT * FROM DadosEmpresa {query_conditions} LIMIT {per_page} OFFSET {(page - 1) * per_page}"
    
    cur.execute(query_sql, params)
    empresas = cur.fetchall()
    
    conn.close()
    
    return render_template('search.html', empresas=empresas, total_results=total_results, total_pages=total_pages, current_page=page, query=query, nome_empresa=nome_empresa, nif=nif, regiao=regiao)

@bp.route('/<int:nif>')
def empresa(nif):
    # seu código para buscar os detalhes da empresa pelo NIF e renderizar um template
    pass
