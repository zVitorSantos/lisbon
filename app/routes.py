from flask import render_template, request, Blueprint
import random
import sqlite3

bp = Blueprint('routes', __name__)

@bp.route('/', methods=['GET', 'POST']) 
def index():

    nome_empresa = request.args.get('nome_empresa', '')
    nif = request.args.get('nif', '')
    
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    query = "SELECT * FROM DadosEmpresa WHERE (AcercaDaEmpresa != 'Informação não encontrada' AND CAE != 'Informação não encontrada') AND CapitalSocial >= 1000;"
    params = []
    if nome_empresa:
        query += "AND Designacao LIKE ? "
        params.append(f"%{nome_empresa}%")
    if nif:
        query += "AND NIF = ? "
        params.append(nif)
    
    cur.execute(query, params)
    empresas = cur.fetchall()
    empresas_selecionadas = random.sample(empresas, min(len(empresas), 4))  
    conn.close()
    
    return render_template('index.html', empresas=empresas_selecionadas)

@bp.route('/s', methods=['GET'])
def search():
    query = request.args.get('query', '').strip()
    
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    
    query_sql = "SELECT * FROM DadosEmpresa WHERE 1=1 "
    params = []
    if query.isdigit():
        # Se a query for composta apenas por dígitos, assuma que é um NIF
        query_sql += "AND NIF = ? "
        params.append(query)
    else:
        # Caso contrário, assuma que é um nome de empresa
        query_sql += "AND Designacao LIKE ? "
        params.append(f"%{query}%")
    
    cur.execute(query_sql, params)
    empresas = cur.fetchall()
    conn.close()
    
    return render_template('search.html', empresas=empresas)

@bp.route('/<int:nif>')
def empresa(nif):
    # seu código para buscar os detalhes da empresa pelo NIF e renderizar um template
    pass
