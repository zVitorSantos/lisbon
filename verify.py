from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from pdfminer.high_level import extract_text
import sqlite3
from bs4 import BeautifulSoup
import re
import pandas as pd
import os
import tabula
import time
import requests
from datetime import datetime

############################################
###### Atualiza as outras informações ######
############################################

# Função para realizar web scraping com Selenium e atualizar as informações na base de dados
def web_scraping(nif, driver):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Encontre a caixa de busca pelo ID "header-search" e insira o NIF
    search_box = driver.find_element('id', 'header-search')
    search_box.clear()  # Limpe qualquer texto anterior
    search_box.send_keys(str(nif))

    driver.implicitly_wait(3)

    # Encontre o botão de pesquisa usando o seletor CSS e clique nele
    try:
        search_button = driver.find_element('css selector', '.search__results a.search__link')
        search_button.click()
    except NoSuchElementException:
        print(f"Nenhum resultado encontrado para a pesquisa do NIF: {nif}")
        return  # Retorna para a próxima iteração se não encontrar resultado

    # Aguarde alguns segundos para a página carregar completamente (ajuste conforme necessário)
    driver.implicitly_wait(3)

    # Use o BeautifulSoup para analisar o HTML da página
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Morada
    morada_element = soup.find('div', class_='px-md--2 detail__line f--grow')
    if morada_element:
        morada = morada_element.find('p', class_='t--d-blue').text
    else:
        morada = "Informação não encontrada"

    # Encontre os elementos com a classe 'detail__key-info'
    key_info_elements = soup.find_all('p', class_='detail__key-info')

    # Inicialize as variáveis como "Informação não encontrada"
    forma_juridica = "Informação não encontrada"
    capital_social = ""

    # Percorra os elementos e verifique o texto
    for element in key_info_elements:
        text = element.get_text()
        if "Forma Jurídica" in text:
            # Encontrou 'Forma Jurídica', então pegue o próximo elemento 't--d-blue'
            forma_juridica = element.find_next('p', class_='t--d-blue').get_text()
        elif "Capital Social" in text:
            # Encontrou 'Capital Social', então pegue o próximo elemento 't--d-blue'
            raw_capital_social = element.find_next('p', class_='t--d-blue').get_text()
            # Remove o símbolo de euro e espaços
            capital_social = re.sub(r'[€\s]', '', raw_capital_social)
            # Verifique se o valor resultante é numérico ou se é 'Não disponível'
            if capital_social.isdigit():
                # Converta a string numérica para um inteiro
                capital_social = int(capital_social)
            elif capital_social == 'Não disponível':
                # Defina capital_social como NULL ou uma string vazia
                capital_social = ""  # ou capital_social = ""
            else:
                # Caso contrário, log ou handle qualquer outra situação inesperada
                print(f"Valor inesperado para Capital Social: {capital_social}")
                capital_social = ""

    # Atividade
    atividade_element = soup.find('p', id='activity', class_='t--d-blue')
    if atividade_element:
        atividade = atividade_element.text
    else:
        atividade = "Informação não encontrada"
            
    #Acerca da Empresa
    acerca_element = soup.find('p', id='about', class_='t--d-blue')
    if acerca_element:
        acerca_da_empresa = acerca_element.text
    else:
        acerca_da_empresa = "Informação não encontrada"

    # Encontre o elemento ul com a classe 't--d-blue'
    cae_ul_element = soup.find('ul', class_='t--d-blue')

    if cae_ul_element:
        # Encontre todos os elementos span com a classe 't--orange f--600' dentro do ul
        cae_span_elements = cae_ul_element.find_all('span', class_='t--orange f--600')

        # Inicialize uma lista para armazenar os CAEs
        caes = []

        for cae_span_element in cae_span_elements:
            cae = cae_span_element.text
            caes.append(cae)

        if caes:
            # Se houver CAEs, você pode convertê-los em uma string separada por vírgulas
            cae = ', '.join(caes)
        else:
            cae = "Informação não encontrada"
    else:
        cae = "Informação não encontrada"

    # Após coletar todas as informações do primeiro site, vá para o segundo site
    second_site_url = f"https://www.einforma.pt/servlet/app/portal/ENTP/prod/ETIQUETA_EMPRESA/nif/{nif}"
    driver.get(second_site_url)
    
    # Dê tempo para a página carregar
    driver.implicitly_wait(3)

    # Colete a URL do site da empresa
    try:
        website_element = driver.find_element(By.CSS_SELECTOR, "td.website span.url a")
        website_url = website_element.get_attribute("href")
    except NoSuchElementException:
        print(f"Não foi possível encontrar a URL do site para o NIF: {nif}")
        website_url = "Não possúi."
        
    print(f"Website URL coletada: {website_url}")

    processar_cae(caes, driver)

    # Atualize a base de dados com a nova informação
    sql_update = """
    UPDATE DadosEmpresa
    SET Morada=?, FormaJuridica=?, CapitalSocial=?, Atividade=?, AcercaDaEmpresa=?, CAE=?, Site=?
    WHERE NIF=?
    """
    cursor.execute(sql_update, (morada, forma_juridica, capital_social, atividade, acerca_da_empresa, cae, website_url, nif))
    conn.commit()

###########################
###### Processar CAE ######
###########################

def processar_cae(cae, driver):
    # Ir para o URL inicial
    driver.get("https://smi.ine.pt/Versao")

    # Preencher o campo de busca com "554"
    search_box = driver.find_element(By.ID, "Codigo")
    search_box.clear()
    search_box.send_keys(str(cae))

    # Clicar no botão de pesquisa
    search_button = driver.find_element(By.CSS_SELECTOR, "input[type='submit'][value='Pesquisar']")
    search_button.click()

    try:
        # Localizar todos os elementos na coluna "ActionCol"
        action_col_elements = driver.find_elements(By.CSS_SELECTOR, "td.ActionCol a.btn")

        # Verificar se pelo menos dois elementos foram encontrados
        if len(action_col_elements) >= 2:
            # Clicar no segundo elemento (índice 1)
            action_col_elements[1].click()
        else:
            print("Não há elementos suficientes na coluna 'ActionCol'.")

        # Clicar no elemento com href='#ui-tabs-2'
        element = driver.find_element(By.CSS_SELECTOR, "a[href='#ui-tabs-2']")
        driver.execute_script("arguments[0].click();", element)

    except Exception as e:
        print(f"Ocorreu um erro: {e}")

    # Conectar ao banco de dados
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # DataFrame para armazenar resultados
    resultados = pd.DataFrame(columns=['CAE', 'Resumo', 'Nota'])

    # Lista para armazenar códigos já pesquisados
    cae_pesquisados = []

    # Loop para iterar através dos códigos CAE únicos
    for cae in cae:
        # Dividir os códigos CAE separados por vírgulas
        for single_cae in str(cae).split(","):
            single_cae = single_cae.strip()
            
            # Verificar se é um número e se tem entre 4 e 5 dígitos
            if not single_cae.isdigit() or not 4 <= len(single_cae) <= 5:
                print(f"Pulando: {single_cae}")
                continue

            # Verificar se já foi pesquisado
            if single_cae in cae_pesquisados:
                #print(f"Pulando {single_cae} pois já foi pesquisado.")
                continue

            # Adicionar ao histórico de pesquisa
            cae_pesquisados.append(single_cae)

            wait = WebDriverWait(driver, 10)
            search_box = wait.until(EC.element_to_be_clickable((By.ID, "CategoriaCod")))
            search_box.clear()
            search_box.send_keys(single_cae)
            
            try:
                # Localizar o botão de pesquisa e aguardar até que ele esteja presente
                element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='submit'][value='Pesquisar']"))
                )
                driver.execute_script("arguments[0].click();", element)
            except StaleElementReferenceException:
                # Se o elemento ficou obsoleto, tentar localizá-lo novamente
                element = driver.find_element(By.CSS_SELECTOR, "input[type='submit'][value='Pesquisar']")
                driver.execute_script("arguments[0].click();", element)
            
            # Loop principal para iterar
            try:
                # Aguardar até que o primeiro elemento "even" na tabela esteja visível
                element = WebDriverWait(driver, 20).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, "table.ListTable.zebra-striped tbody tr.even:first-child td a[data-ajax='true']"))
                )
                
                # Se o elemento está visível, prosseguir com as operações
                resumo = element.text
                driver.execute_script("arguments[0].click();", element)

                # Esperar até que o elemento da "Nota" seja carregado
                nota_element = WebDriverWait(driver, 20).until(
                    EC.visibility_of_element_located((By.XPATH, "//td[normalize-space(text())='Nota']/following-sibling::td"))
                )
                nota = nota_element.text
                
                # Tentar fechar o modal
                close_button = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//button/span[text()='Fechar']/.."))
                )
                driver.execute_script("arguments[0].click();", close_button)

                # Quando for salvar no banco de dados, use 'single_cae' em vez de 'cae'
                cursor.execute("INSERT INTO CAE (CAE, Resumo, Nota) VALUES (?, ?, ?)", (single_cae, resumo, nota))
                conn.commit()

                print(f"Sucesso na busca do CAE: {single_cae}!")

            except TimeoutException:
                print(f"Campo 'Nota' não foi encontrado para o CAE {cae}. Pulando para o próximo.")
            except Exception as e:
                print(f"Nenhum resultado encontrado para {cae}. Erro: {e}")

    # Fechar o navegador
    driver.close()

############################
###### Loop por todos ######
############################

def loop_scraping():
    options = webdriver.FirefoxOptions()
    options.add_argument('-headless')
    driver = webdriver.Firefox(options=options)

    # Acesse a página "https://www.racius.com/observatorio/"
    driver.get('https://www.racius.com/observatorio')

    print("Iniciou...")
    
    # Conecte ao banco de dados
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Consulte a base de dados para obter a lista de NIFs
    cursor.execute("SELECT NIF FROM DadosEmpresa")
    nifs = cursor.fetchall()

    # Inicialize uma variável contadora
    busca_numero = 1

    # Itere sobre os NIFs e realize o web scraping
    for nif in nifs:
        print(f"Iniciando busca {busca_numero}...")
        busca_numero += 1

        # Execute o web scraping
        web_scraping(nif[0], driver)

    # Feche o driver do Firefox após concluir todas as buscas
    driver.quit()

    # Feche a conexão com o banco de dados
    conn.close()

#########################
###### BUSCA O PDF ######
#########################

def buscar_pdf():
    current_date = datetime.now().strftime("%d-%m-%Y")
    directory = f"pdf/{current_date}"
    if os.path.exists(directory):
        print("A pasta com a data atual já existe. O programa será encerrado.")
        exit()

    start_drive = time.time()

    # Configurações do WebDriver
    options = webdriver.FirefoxOptions()
    options.set_preference("browser.download.folderList", 2)
    options.set_preference("browser.download.manager.showWhenStarting", False)
    options.set_preference("browser.download.dir", os.path.abspath("pdf"))
    options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/pdf")

    # Inicializar o driver do navegador
    options.add_argument('-headless')
    driver = webdriver.Firefox(options=options)

    end_drive = time.time()
    duration = end_drive - start_drive
    print(f"DRIVE: {format(duration, '.4f')}s")

    # Acessar o site
    driver.get("https://www.iapmei.pt/PRODUTOS-E-SERVICOS/Empreendedorismo-Inovacao/Empreendedorismo-(1)/Tech-Visa.aspx")

    # Aguardar alguns segundos para que a página seja carregada
    time.sleep(5)

    # Encontrar o link do PDF
    try:
        pdf_link_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.PARTIAL_LINK_TEXT, "Lista de empresas certificadas TECH VISA"))
        )
        pdf_url = pdf_link_element.get_attribute("href")
    except Exception as e:
        print(f"Erro ao tentar encontrar o link do PDF: {e}")

    # Fechar o navegador
    driver.close()

    print("Criando pasta da data atual...")

    # Criar a pasta com a data atual se ela não existir
    current_date = datetime.now().strftime("%d-%m-%Y")
    directory = f"pdf/{current_date}"
    if not os.path.exists(directory):
        os.makedirs(directory)

    print("Pasta criada.\nBaixando PDF...")

    # Baixar o PDF diretamente para a pasta específica
    response = requests.get(pdf_url)
    pdf_file_path = f"{directory}/{current_date}.pdf"
    with open(pdf_file_path, 'wb') as f:
        f.write(response.content)

    # Caminho para o arquivo PDF
    caminho_pdf = f"{directory}/{current_date}.pdf"

    print("PDF baixado.\nColetando dados...")

    # Extrair texto do PDF com pdfminer
    texto = extract_text(caminho_pdf)

    # Utilize expressão regular para extrair NIF e Nome da Empresa
    empresas = re.findall(r'(\d{9})\s+(.+?)\n', texto)

    # Criar um DataFrame com as duas primeiras colunas
    df_pdfminer = pd.DataFrame(empresas, columns=['NIF', 'Nome da Empresa'])

    # Extrair tabelas do PDF para uma lista de DataFrames
    dfs = tabula.read_pdf(caminho_pdf, pages='all', multiple_tables=True)

    # Concatenar todos os DataFrames em um único DataFrame
    df_tabula = pd.concat(dfs, ignore_index=True)

    # Limpar os nomes das colunas
    df_tabula.columns = df_tabula.columns.str.replace(r'[^a-zA-Z ]', '', regex=True).str.strip()

    # Renomear as colunas conforme necessário
    df_tabula.columns = ['NIF', 'Nome da Empresa', 'Data Inicial', 'Data Final']

    print("Informações coletadas.\nCriando planilha...")

    if 'Data Inicial' in df_tabula.columns and 'Data Final' in df_tabula.columns:
        # Mantenha apenas as colunas de data
        df_tabula = df_tabula[['Data Inicial', 'Data Final']]

        # Concatenar os dois DataFrames horizontalmente
        df_final = pd.concat([df_pdfminer, df_tabula], axis=1)

        # Exportar para Excel
        df_final.to_excel(f"{directory}/{current_date}.xlsx", index=False)
        print("Planilha gerada!")
    else:
        print("As colunas 'Data Inicial' e 'Data Final' não foram encontradas em df_tabula.")

    ########################################
    ###### Verificações/Updates no DB ######
    ########################################

    print("Abrindo DB...")

    # Conectar ao banco de dados SQLite
    con = sqlite3.connect("database.db")
    cur = con.cursor()

    # Obter todos os NIFs do banco de dados
    cur.execute("SELECT NIF FROM DadosEmpresa")
    nifs_df = set(df_final['NIF'].astype(str))
    nifs_db = set([str(row[0]) for row in cur.fetchall()])

    # Encontrar NIFs que estão no banco de dados mas não estão no DataFrame df_final
    nifs_missing_in_df = nifs_db.difference(nifs_df)

    # Imprimir os NIFs que estão faltando no DataFrame df_final
    for nif_missing in nifs_missing_in_df:
        print(f"NIF no banco de dados, mas não no arquivo Excel: {nif_missing}")
    else:
        print("Nenhum NIF faltando no .xlsx")

    print("Iniciando verificação de novas empresas...")

    # Iterar pelas linhas do DataFrame para atualizar ou inserir registros
    for i, row in df_final.iterrows():
        nif = row['NIF']
        nome_empresa = row['Nome da Empresa']
        data_inicial = row['Data Inicial']
        data_final = row['Data Final']

        # Verificar se o NIF já existe no banco de dados
        cur.execute("SELECT * FROM DadosEmpresa WHERE NIF=?", (nif,))
        result = cur.fetchone()

        if result:
            # Atualizar registro existente
            cur.execute("UPDATE DadosEmpresa SET DataInicial=?, DataFinal=? WHERE NIF=?", (data_inicial, data_final, nif))
        else:
            # Inserir novo registro
            cur.execute("INSERT INTO DadosEmpresa (NIF, Designacao, DataInicial, DataFinal) VALUES (?, ?, ?, ?)", 
                        (nif, nome_empresa, data_inicial, data_final))
            print(f"Novo NIF adicionado: {nif}, Empresa: {nome_empresa}")

            # Realizar web scraping para o novo NIF
            web_scraping(nif, driver)

        con.commit()

    print("Verificação concluída.\nVerificando validade...")

    cur.execute("SELECT NIF, DataFinal FROM DadosEmpresa")
    registros = cur.fetchall()
    data_atual = datetime.now().date()  # Obtem a data atual

    for registro in registros:
        nif, data_final_str = registro
        # Converte a string de data para um objeto datetime.date
        data_final = datetime.strptime(data_final_str, '%d-%m-%Y').date() if data_final_str else None
        
        # Verifica se a data final é anterior à data atual
        if data_final and data_final < data_atual:
            print(f"A data final do NIF {nif} é anterior à data atual: {data_final}")

    print("Loop de verificação geral concluído, encerrando...")

    # Fechar a conexão com o banco de dados
    con.close()

#buscar_pdf()

#loop_scraping()