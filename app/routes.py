from flask import render_template, request, Blueprint
from flask import redirect, url_for
from math import ceil
from flask import jsonify
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
    cae_resumo = request.args.get('cae_resumo', '').strip()

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

    query_conditions += "OR CAE IN (SELECT CAE FROM CAE WHERE Resumo LIKE ?) "
    params.append(f"%{query}%")

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

@bp.route('/suggestions', methods=['GET'])
def suggestions():
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify([])

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    
    sql = """SELECT DadosEmpresa.Designacao, DadosEmpresa.NIF, DadosEmpresa.CAE, CAE.Resumo 
             FROM DadosEmpresa 
             JOIN CAE ON DadosEmpresa.CAE = CAE.CAE
             WHERE DadosEmpresa.Designacao LIKE ? OR DadosEmpresa.NIF LIKE ? OR CAE.Resumo LIKE ?"""
    params = [f"%{query}%", f"%{query}%", f"%{query}%"]
    cur.execute(sql, params)
    results = cur.fetchall()
    conn.close()

    suggestions = []
    for r in results:
        suggestions.append({
            'nome': r[0],
            'nif': r[1],
            'cae': r[2],
            'resumo_cae': r[3]
        })

    return jsonify(suggestions)

@bp.route('/<int:nif>')
def empresa(nif):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Buscar informações da empresa
    cursor.execute('SELECT * FROM DadosEmpresa WHERE NIF = ?', (nif,))
    empresa = cursor.fetchone()

    # Buscar informações do CAE
    if empresa:
        cursor.execute('SELECT * FROM CAE WHERE CAE = ?', (empresa[7],))  # O índice 7 corresponde à coluna CAE na tabela DadosEmpresa
        cae_info = cursor.fetchone()
    else:
        cae_info = None

    conn.close()

    if empresa is None:
        return "Empresa não encontrada", 404

    return render_template('empresa.html', empresa=empresa, cae_info=cae_info, website_url=empresa[8])
