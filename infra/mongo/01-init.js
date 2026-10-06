const training = db.getSiblingDB('midas_training');
training.createUser({user:'midas_app', pwd:process.env.MONGO_APP_PASSWORD,
  roles:[{role:'readWrite', db:'midas_training'}]});
training.createCollection('datasets', {validator: {$jsonSchema: {
  bsonType:'object', required:['_id','name','version','source','is_demo','created_at'],
  properties: {_id:{bsonType:'string'}, name:{bsonType:'string'}, version:{bsonType:'string'},
    source:{bsonType:'string'}, is_demo:{bsonType:'bool'}, created_at:{bsonType:'date'}}
}}});
training.datasets.createIndex({name:1, version:1}, {unique:true});
training.createCollection('training_samples', {validator: {$jsonSchema: {
  bsonType:'object', required:['dataset_id','ticker','as_of','label_end','horizon_months','features','target'],
  properties:{dataset_id:{bsonType:'string'}, ticker:{bsonType:'string'},
    as_of:{bsonType:'date'}, label_end:{bsonType:'date'}, horizon_months:{enum:[6,12,24,36]},
    features:{bsonType:'object'}, target:{bsonType:['double','int','long','decimal']}}
}}});
training.training_samples.createIndex({dataset_id:1,ticker:1,as_of:1,horizon_months:1},{unique:true});
training.training_samples.createIndex({dataset_id:1,as_of:1,label_end:1});
training.createCollection('model_artifacts', {validator: {$jsonSchema: {
  bsonType:'object', required:['_id','dataset_id','created_at','parameters'],
  properties:{_id:{bsonType:'string'},dataset_id:{bsonType:'string'},created_at:{bsonType:'date'},parameters:{bsonType:'object'}}
}}});
training.model_artifacts.createIndex({dataset_id:1,created_at:-1});
