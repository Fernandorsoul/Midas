"""Verifica autenticação e escrita com usuários da aplicação, sem expor senhas."""
import subprocess

def run(service, command):
    subprocess.run(['docker', 'compose', 'exec', '-T', service, *command], check=True)

run('postgres', ['sh', '-c', '''PGPASSWORD="$APP_PASSWORD" psql -h 127.0.0.1 -U midas_app -d midas -v ON_ERROR_STOP=1 -c "BEGIN; INSERT INTO assets(ticker,name,category,sector,is_demo) VALUES ('__HEALTHCHECK__','Verificação','stock','Teste',true); ROLLBACK; SELECT count(*) AS tabelas FROM information_schema.tables WHERE table_schema='public';"'''])
run('mongodb', ['mongosh', '--quiet', '--eval', '''
const d=db.getSiblingDB('midas_training');
if(!d.auth('midas_app',process.env.MONGO_APP_PASSWORD)) throw Error('Autenticação falhou');
const id='__healthcheck__'+new ObjectId().toString();
try {
 d.datasets.insertOne({_id:id,name:id,version:'test',source:'healthcheck',is_demo:true,created_at:new Date()});
 if(!d.datasets.findOne({_id:id})) throw Error('Leitura falhou');
 print('MongoDB: autenticação, escrita e leitura OK; coleções: '+d.getCollectionNames().join(', '));
} finally { d.datasets.deleteOne({_id:id}); }
'''])
print('PostgreSQL e MongoDB prontos.')
