from iqoptionapi.stable_api import IQ_Option
import time, json, sys, logging, configparser, threading
from datetime import datetime
from dateutil import tz
from bs4 import BeautifulSoup
from time import mktime
import requests

# Desativar o DEBUG/ERROR
#logging.disable(level=(logging.ERROR))
#logging.basicConfig(level=logging.DEBUG,format='%(asctime)s %(message)s')

def configuracao():
    arquivo = configparser.RawConfigParser()
    arquivo.read('config.txt')
    
    return {'login': arquivo.get('GERAL', 'login'), 'senha': arquivo.get('GERAL', 'senha'), 'tipoconta': arquivo.get('GERAL', 'tipoconta'), 'delayentrada': arquivo.get('GERAL', 'delayentrada'), 'tempo_noticia': arquivo.get('GERAL', 'TempoNoticia')}

# carregar configurações
configuracoes = configuracao()

# conectar à iq e iniciar api
print('\nConectando à IqOption... \n')
API = IQ_Option(configuracoes['login'], configuracoes['senha'])

API.connect()

while True:
    if API.check_connect() == False:
        print('Erro ao se conectar\n')
    else:
        print('Conectado com sucesso\n')
        break
	
    time.sleep(1)

# Mudar conta real e treinamento. REAL ou PRACTICE
API.change_balance(configuracoes['tipoconta'])

# função para capturar perfil
def perfil():
    perfil = json.loads(json.dumps(API.get_profile_ansyc()))
    
    return perfil

# função pra converter tempo
def timestamp_converter(x, y):
    x += y #se precisar diminuir tempo
    hora = datetime.strptime(datetime.utcfromtimestamp(x).strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S')
    hora = hora.replace(tzinfo=tz.gettz('GMT'))
        
    return str(hora.astimezone(tz.gettz('America/Sao Paulo')))[:-6]

# função pra pegar o valor da banca
def banca():
    return API.get_balance()
        

# carregar sinais da lista txt
# formato: tempo, paridade, direção, valor, tempo, quantidade de gales
def carregar_sinais():

    arquivo = open('sinais.txt', encoding='UTF-8')
    lista = arquivo.read()
    arquivo.close
    
    lista = lista.split('\n')
    
    for index,a in enumerate(lista):
        if a == '':
            del lista[index]
            
    return lista

def TemNoticia():

    headers = requests.utils.default_headers()
    headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.83 Safari/537.36 Edg/85.0.564.41'})
    data = requests.get('http://br.investing.com/economic-calendar/', headers=headers)

    resultados = []

    if data.status_code == requests.codes.ok:
        info = BeautifulSoup(data.text, 'html.parser')

        blocos = ((info.find('table', {'id': 'economicCalendarData'})).find('tbody')).findAll('tr', {'class': 'js-event-item'})
            
        for blocos2 in blocos:
            impacto = str((blocos2.find('td', {'class': 'sentiment'})).get('data-img_key')).replace('bull', '')
            horario = str(blocos2.get('data-event-datetime'))[11:16]
            moeda = (blocos2.find('td', {'class': 'left flagCur noWrap'})).text.strip()
            if impacto == '3':
                hora_entrada_unix = int(mktime(datetime.strptime(datetime.now().strftime('%Y/%m/%d')+' '+horario+':00',  "%Y/%m/%d %H:%M:%S").timetuple()))
                resultados.append({moeda+str(hora_entrada_unix)})

    return resultados

def entrada(opcao_entrada, hora_entrada, par_entrada, valor_entrada, direcao_entrada, tempo_entrada, gale_entrada, gale_multiplicador):
    gale_entrada = int(gale_entrada)
    
    if opcao_entrada == 'digital':
        _,id = API.buy_digital_spot(par_entrada, valor_entrada, direcao_entrada, tempo_entrada)
        
        if isinstance(id, int):
            while True:
                status,lucro_entrada = API.check_win_digital_v2(id)
                
                if status:
                    if lucro_entrada > 0:
                        return 'Win',round(int(valor_entrada), 2)
                    else:
                        return 'Loss',0
                    break        
    else:
        status,id = API.buy(int(valor_entrada), str(par_entrada), str(direcao_entrada), int(tempo_entrada))
        #print(id)
        if status:
            
            tempo_restante=API.get_remaning(int(tempo_entrada)) # pega o tempo restante pra dar uma pausa
            #print('Pausinha de ', tempo_restante, ' segundos')
            #time.sleep(int(tempo_restante)-5) # pausinha pra n ficar checando sempre
            status,lucro_entrada = API.check_win_v4(id)
            #print(status)
                        
            if lucro_entrada > 0:
                print('## '+hora_entrada[0:5]+' '+par_entrada+': Win - Lucro: R$ '+str(lucro_entrada)+' ')
            elif status == 'equal':
                print('## '+hora_entrada[0:5]+' '+par_entrada+': Empate - Lucro: R$ '+str(lucro_entrada)+' ')
            else:            
                if gale_entrada > 0:                                                       
                    print('## '+hora_entrada[0:5]+' '+par_entrada+': Loss - Lucro: '+str(int(valor_entrada)*-1)+' ')
                    
                    i = 1
                    while i <= int(gale_entrada): # Gale, essa variavel foi passada na função
                        
                        print('### '+hora_entrada[0:5]+' '+par_entrada+': Gale '+str(i)+' de '+str(gale_entrada)+' - Multiplicador '+str(gale_multiplicador)+'x. Aguardando resultado.')
                        status,id = API.buy(int(valor_entrada)*int(gale_multiplicador), str(par_entrada), str(direcao_entrada), int(tempo_entrada))                                           
                        tempo_restante=API.get_remaning(int(tempo_entrada)) # pega o tempo restante pra dar uma pausa
                        #print('Pausinha de ', tempo_restante, ' segundos')
                        #time.sleep(int(tempo_restante)-5) # pausinha
                        status,lucro_entrada = API.check_win_v4(id)                        
                        if lucro_entrada > 0: # se o preço no inicio for menor que o preço no fim                                                      
                            print('#### '+hora_entrada[0:5]+' '+par_entrada+' - Gale '+str(i)+' de '+str(gale_entrada)+' do sinal '+par_entrada+' às '+hora_entrada[0:5]+' : Win - Lucro: R$ '+str(lucro_entrada)+' ')            
                            break
                        elif i < int(gale_entrada):
                            print('#### '+hora_entrada[0:5]+' '+par_entrada+' - Gale '+str(i)+' de '+str(gale_entrada)+' do sinal '+par_entrada+' às '+hora_entrada[0:5]+' : Loss - Lucro: R$ '+str(int(valor_entrada)*int(gale_multiplicador)*-1)+' ')
                        else:
                            print('#### '+hora_entrada[0:5]+' '+par_entrada+' - Gale '+str(i)+' de '+str(gale_entrada)+' do sinal '+par_entrada+' às '+hora_entrada[0:5]+' : Loss - Lucro: R$ '+str(int(valor_entrada)*int(gale_multiplicador)*-1)+' ')
                            break
                        
                        gale_multiplicador = int(gale_multiplicador) * 2
                        i += 1   
                else:
                    print('## '+hora_entrada[0:5]+' '+par_entrada+': Loss - Lucro: R$ '+str(lucro_entrada)+' ')
        else:
            print('## '+hora_entrada[0:5]+' '+par_entrada+': Erro ao dar entrada')       

## print(json.dumps(carregar_sinais(), indent=1))

###########################################################################################
###########################################################################################

# inicio das entradas do bot

print('Aguardando o horário dos sinais...\n')
print('Legenda:\n# : Entrada\n## : Resultado\n### : Gale\n#### : Resultado Gale\n')

lista_sinais = carregar_sinais()

sinais_efetuados = {'sinais efetuados'}

noticias = TemNoticia()

while True: # roda o script infinitamente
    for sinal in lista_sinais: # loop das linhas do txt
        sinais_separados = sinal.split(',')
        data_hora_agora = timestamp_converter(time.time(), +60) # pega a hora, minuto e segundo atual (acrescenta 1 minuto, porque o sinal é dado 1 min antes
        delay_entrada = 59-int(configuracoes['delayentrada']) # diminui o tempo de delay configurado no arquivo txt
        entrada_tempo_s = sinais_separados[0] + ':' + str(delay_entrada)
        entrada_tempo_s2 = sinais_separados[0] + ':' + str(int(delay_entrada)-1)
        
        # converte o tempo em unixtime
        hora_entrada_unix = int(mktime(datetime.strptime(datetime.now().strftime('%Y/%m/%d')+' '+sinais_separados[0]+':00',  "%Y/%m/%d %H:%M:%S").timetuple()))

        # não entrar contra notícias
        tempo_noticia = int(configuracoes['tempo_noticia'])*60
        temnoticiapar = False
        for noticia in noticias:
            # se estiver no par e estiver até 15 min antes ou até 15 min dps de noticias
            if sinais_separados[1][0:3] == str(noticia)[2:5] and hora_entrada_unix >= int(str(noticia)[5:15])-tempo_noticia and hora_entrada_unix <= int(str(noticia)[5:15])+tempo_noticia:
                temnoticiapar = True
                break
            elif sinais_separados[1][3:6] == str(noticia)[2:5] and hora_entrada_unix >= int(str(noticia)[5:15])-tempo_noticia and hora_entrada_unix <= int(str(noticia)[5:15])+tempo_noticia:
                temnoticiapar = True
                break 
        
        
        # se estiver na hora do sinal e segundo 58 ou 59 e se o sinal não estiver no set sinais efetuados
        # if data_hora_agora[11:20] == entrada_tempo_s2 and sinal not in sinais_efetuados or data_hora_agora[11:20] == entrada_tempo_s and sinal not in sinais_efetuados: # se a entrada for igual o horario atual       
        if data_hora_agora[11:20] == entrada_tempo_s and sinal not in sinais_efetuados: # se a entrada for igual o horario atual
            
            if temnoticiapar == False:

                print('#', sinais_separados[0], sinais_separados[1], ': aguardando resultado.')           
                t = threading.Thread(target=entrada,args=('binaria', data_hora_agora[11:18], sinais_separados[1], sinais_separados[3], sinais_separados[2], sinais_separados[4], sinais_separados[5], sinais_separados[6]))
                t.start()
                sinais_efetuados.add(sinal)
                time.sleep(0.1)

            else:
                sinais_efetuados.add(sinal)
                print('##', sinais_separados[0], sinais_separados[1], ': Noticia detectada (entrada não efetuada)')
                time.sleep(0.1)
        # else:
        # print('ainda não')
        

####### verificar todos tempos e adicionar time.sleep pra não precisar ficar checando toda hora
