"""D02 true artifacts/inference, deployment gates and explicit monitoring windows."""
import base64,copy,json,os,sqlite3,tempfile,threading,time,unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from shared.mlops_workspace import MlopsWorkspace,WorkspaceError,infer,parse_csv,sample_csv,digest

class MlopsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template=tempfile.TemporaryDirectory();w=MlopsWorkspace(cls.template.name,False);cls.data=w.create_sample({})['dataset_id'];cls.models=[];cls.experiments=[]
        for c in (1,.2):
            j=w.train({'dataset':cls.data,'c':c,'name':'固定切分实验 '+str(c)})['job_id'];w.process_one();result=w.job(j);assert result['status']=='succeeded',result;cls.models.append(result['result']['model_id']);cls.experiments.append(result['result']['experiment_id'])
        w.close()
    @classmethod
    def tearDownClass(cls):cls.template.cleanup()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        with sqlite3.connect(Path(self.template.name)/'mlops.sqlite3') as src,sqlite3.connect(Path(self.temp.name)/'mlops.sqlite3') as dst:src.backup(dst)
        self.w=MlopsWorkspace(self.temp.name,False)
    def tearDown(self):self.w.close();self.temp.cleanup()
    def approve(self,id):
        m=self.w.model(id);return self.w.review_model(id,{'revision':m['review_revision'],'sha':m['sha'],'decision':'approved','actor':'测试审核','comment':'核对数据、切分、适用范围与模型制品'})
    def deploy(self,id,rollback=False):
        self.approve(id);j=self.w.deploy({'model':id,'revision':self.w.health()['revision'],'actor':'测试操作','comment':'切换后核对真实预测','rollback':rollback})['job_id'];self.w.process_one();self.assertEqual(self.w.job(j)['status'],'succeeded',self.w.job(j));return j
    def window(self,profile):
        ds=self.w.create_sample({'profile':profile})['dataset_id'];j=self.w.monitor({'dataset':ds,'revision':self.w.health()['revision']})['job_id'];self.w.process_one();self.assertEqual(self.w.job(j)['status'],'succeeded',self.w.job(j));return self.w.window(self.w.job(j)['result']['window_id'])
    def row(self):return {'feature_1':.5,'feature_2':-.2,'feature_3':.3,'feature_4':0}
    def test_immutable_data_hash_and_dedup(self):
        r=self.w.create_sample({});self.assertEqual(r['dataset_id'],self.data);self.assertTrue(r['deduplicated']);d=self.w.dataset(self.data);self.assertEqual(d['origin'],'synthetic');self.assertEqual(len(d['data']['rows']),600)
    def test_upload_revision_is_new_snapshot(self):
        r=self.w.import_dataset({'title':'修订','filename':'data.csv','parent':self.data,'text':sample_csv('training',seed=43).decode()});self.assertNotEqual(r['dataset_id'],self.data);self.assertEqual(self.w.dataset(r['dataset_id'])['parent'],self.data);self.assertNotEqual(self.w.dataset(r['dataset_id'])['sha'],self.w.dataset(self.data)['sha'])
    def test_csv_invalid_schema_and_encoding(self):
        for raw,kind,label in [(b'\xff','training','label'),(b'x,x,label\n1,2,1','training','label'),(b'x,label\n1,0,extra','monitoring','label'),(b'x,label\nnan,1','training','label'),(b'x,label\n1,2','training','label')]:
            with self.subTest(raw=raw):
                with self.assertRaises(WorkspaceError):parse_csv(raw,kind,label)
    def test_monitoring_preserves_missing_and_bad_labels(self):
        v=parse_csv(b'x,label\n,1\ninf,2\n0.5,\n1,0','monitoring','label');self.assertEqual(v['quality']['invalid_feature_rows'],2);self.assertEqual(v['quality']['invalid_labels'],1);self.assertIsNone(v['labels'][2])
    def test_same_split_for_paired_experiments_and_no_leakage(self):
        a,b=[self.w.experiment(e) for e in self.experiments];self.assertEqual(a['split'],b['split']);self.assertFalse(set(a['split']['train'])&set(a['split']['validation']));self.assertEqual(len(a['split']['train'])+len(a['split']['validation']),600)
        data=self.w.dataset(self.data)['data'];m=self.w.model(self.models[0]);mean=sum(data['rows'][i]['feature_1'] for i in a['split']['train'])/len(a['split']['train']);self.assertAlmostEqual(m['artifact']['mean'][0],mean)
    def test_reloaded_json_matches_holdout_metrics(self):
        m=self.w.model(self.models[0]);e=m['experiment'];d=self.w.dataset(self.data)['data'];ids=e['split']['validation'];outputs=infer(m['artifact'],[d['rows'][i] for i in ids]);accuracy=sum(o['prediction']==d['labels'][i] for o,i in zip(outputs,ids))/len(ids);self.assertAlmostEqual(accuracy,e['metrics']['accuracy']);self.assertEqual(digest(json.dumps(m['artifact'],sort_keys=True,ensure_ascii=False,allow_nan=False)),m['sha'])
    def test_model_requires_approval(self):
        with self.assertRaises(WorkspaceError):self.w.deploy({'model':self.models[0],'revision':0,'actor':'操作','comment':'不能绕过审核'})
    def test_quality_gate_cannot_be_approved(self):
        j=self.w.train({'dataset':self.data,'min_accuracy':1})['job_id'];self.w.process_one();m=self.w.model(self.w.job(j)['result']['model_id']);self.assertFalse(m['experiment']['gate'])
        with self.assertRaises(WorkspaceError):self.w.review_model(m['id'],{'revision':0,'sha':m['sha'],'decision':'approved','actor':'审核','comment':'门禁不足'})
    def test_review_optimistic_concurrency(self):
        m=self.w.model(self.models[0])
        def review(i):
            try:self.w.review_model(m['id'],{'revision':0,'sha':m['sha'],'actor':'审核'+str(i),'comment':'核对通过','decision':'approved'});return 1
            except WorkspaceError:return 0
        with ThreadPoolExecutor(max_workers=2) as pool:self.assertEqual(sum(pool.map(review,range(2))),1)
    def test_real_predict_reports_actual_version_for_100_requests(self):
        self.deploy(self.models[0]);expected=infer(self.w.model(self.models[0])['artifact'],[self.row()])[0]
        for i in range(100):
            r=self.w.predict({'rows':[self.row()]});self.assertEqual(r['model_id'],self.models[0]);self.assertEqual(r['deployment_revision'],1);self.assertAlmostEqual(r['predictions'][0]['probability'],expected['probability'])
        self.assertEqual(self.w.state()['counters']['requests_total'],100)
    def test_deploy_and_rollback_use_historical_weights(self):
        self.deploy(self.models[0]);before=self.w.predict({'rows':[self.row()]});self.deploy(self.models[1]);current=self.w.predict({'rows':[self.row()]});self.assertEqual(current['model_id'],self.models[1]);self.deploy(self.models[0],True);after=self.w.predict({'rows':[self.row()]});self.assertEqual(after['model_id'],self.models[0]);self.assertEqual(after['deployment_revision'],3);self.assertEqual(before['predictions'],after['predictions']);self.assertEqual(self.w.state()['events'][0]['action'],'rollback')
    def test_corrupt_candidate_does_not_replace_service(self):
        self.deploy(self.models[0]);self.approve(self.models[1]);j=self.w.deploy({'model':self.models[1],'revision':1,'actor':'操作','comment':'损坏注入'})['job_id']
        with self.w.connect(True) as c:c.execute('UPDATE models SET artifact=? WHERE id=?',('{invalid',self.models[1]))
        self.w.process_one();self.assertEqual(self.w.job(j)['status'],'failed');self.assertEqual(self.w.health()['model'],self.models[0]);self.assertTrue(self.w.health()['ready']);self.assertEqual(self.w.predict({'rows':[self.row()]})['model_id'],self.models[0]);self.assertEqual(self.w.state()['events'][0]['loaded'],self.models[0])
    def test_bad_active_artifact_is_not_reported_ready(self):
        self.deploy(self.models[0]);self.deploy(self.models[1])
        with self.w.connect(True) as c:c.execute('UPDATE models SET artifact=? WHERE id=?',('{}',self.models[1]))
        self.assertFalse(self.w.health()['ready'])
        with self.assertRaises(WorkspaceError):self.w.predict({'rows':[self.row()]})
        self.deploy(self.models[0],True);self.assertTrue(self.w.health()['ready'])
    def test_two_stale_deployments_cannot_overwrite_each_other(self):
        jobs=[]
        for m in self.models:self.approve(m);jobs.append(self.w.deploy({'model':m,'revision':0,'actor':'操作','comment':'相同基线修订'})['job_id'])
        self.w.process_one();self.w.process_one();self.assertEqual(self.w.job(jobs[0])['status'],'succeeded');self.assertEqual(self.w.job(jobs[1])['status'],'failed');self.assertEqual(self.w.health()['model'],self.models[0])
    def test_revoked_review_blocks_queued_deployment(self):
        self.approve(self.models[0]);m=self.w.model(self.models[0]);j=self.w.deploy({'model':m['id'],'revision':0,'actor':'操作','comment':'待加载'})['job_id'];self.w.review_model(m['id'],{'revision':1,'sha':m['sha'],'actor':'复核','comment':'退回进一步检查','decision':'rejected'});self.w.process_one();self.assertEqual(self.w.job(j)['status'],'failed');self.assertIsNone(self.w.health()['model'])
    def test_unknown_features_nonfinite_and_bool_rejected(self):
        self.deploy(self.models[0])
        for row in [{'other':1},{**self.row(),'feature_1':True},{**self.row(),'feature_1':float('nan')},{**self.row(),'feature_1':1e7}]:
            with self.subTest(row=row):
                with self.assertRaises(WorkspaceError):self.w.predict({'rows':[row]})
        self.assertEqual(self.w.state()['counters']['request_errors_total'],4)
    def test_missing_labels_never_report_accuracy_or_quality_drop(self):
        self.deploy(self.models[0]);w=self.window('missing_labels');r=w['report'];self.assertIsNone(r['accuracy']);self.assertIsNone(r['baseline_accuracy']);self.assertFalse(r['quality_ready']);self.assertNotIn('quality_drop',[a['kind'] for a in w['alerts']]);self.assertIn('labels_missing',[a['kind'] for a in w['alerts']])
    def test_feature_shift_is_distinct_from_effect_drop(self):
        self.deploy(self.models[0]);w=self.window('feature_shift');self.assertIn('feature_drift',[a['kind'] for a in w['alerts']]);self.assertGreater(w['report']['features'][0]['psi'],.2);self.assertNotIn('quality_drop',[a['kind'] for a in w['alerts']])
    def test_label_shift_requires_observed_labels(self):
        self.deploy(self.models[0]);w=self.window('label_shift');self.assertTrue(w['report']['quality_ready']);self.assertLess(w['report']['accuracy'],.2);self.assertIn('quality_drop',[a['kind'] for a in w['alerts']]);self.assertEqual(self.w.health()['model'],self.models[0])
    def test_missing_rows_are_counted_and_skipped(self):
        self.deploy(self.models[0]);w=self.window('missing_values');self.assertEqual(w['report']['total_rows'],600);self.assertEqual(w['report']['valid_rows'],480);self.assertEqual(w['report']['quality']['missing_values'],120);self.assertIn('data_quality',[a['kind'] for a in w['alerts']])
    def test_baseline_uses_exact_same_labeled_rows(self):
        self.deploy(self.models[0]);self.deploy(self.models[1]);w=self.window('clean');data=self.w.dataset(w['dataset'])['data'];pred=infer(self.w.model(self.models[0])['artifact'],data['rows']);expected=sum(o['prediction']==y for o,y in zip(pred,data['labels']))/len(pred);self.assertAlmostEqual(w['report']['baseline_accuracy'],expected);self.assertAlmostEqual(w['report']['accuracy_drop'],expected-w['report']['accuracy'])
    def test_monitoring_snapshot_survives_later_switch(self):
        self.deploy(self.models[0]);w=self.window('clean');before=self.w.export('windows',w['id'])[0];self.deploy(self.models[1]);self.assertEqual(before,self.w.export('windows',w['id'])[0])
    def test_alert_actions_are_audited_and_versioned(self):
        self.deploy(self.models[0]);a=self.window('label_shift')['alerts'][0];self.w.alert_action(a['id'],{'revision':0,'status':'acknowledged','actor':'处理人','comment':'检查标签来源'})
        with self.assertRaises(WorkspaceError):self.w.alert_action(a['id'],{'revision':0,'status':'resolved','actor':'旧页面','comment':'不能覆盖'})
        self.assertEqual(self.w.alert(a['id'])['actions'][0]['status'],'acknowledged')
    def test_cancel_and_retry_are_explicit(self):
        j=self.w.train({'dataset':self.data})['job_id'];self.w.job_action(j,'cancel');self.assertFalse(self.w.process_one());retry=self.w.job_action(j,'retry')['job_id'];again=self.w.job_action(j,'retry')['job_id'];self.assertEqual(retry,again);self.w.process_one();self.assertEqual(self.w.job(retry)['status'],'succeeded')
    def test_interrupted_job_requires_retry(self):
        j=self.w.train({'dataset':self.data})['job_id']
        with self.w.connect(True) as c:c.execute("UPDATE jobs SET status='running',owner='lost',heartbeat=? WHERE id=?",(time.time()-60,j))
        self.w.recover();self.assertEqual(self.w.job(j)['status'],'interrupted');self.assertFalse(self.w.process_one());retry=self.w.job_action(j,'retry')['job_id'];self.w.process_one();self.assertEqual(self.w.job(retry)['status'],'succeeded')
    def test_archival_blocks_new_training_not_historical_inference(self):
        self.deploy(self.models[0]);self.w.archive(self.data)
        with self.assertRaises(WorkspaceError):self.w.train({'dataset':self.data})
        self.assertEqual(self.w.predict({'rows':[self.row()]})['model_id'],self.models[0]);self.assertTrue(self.w.export('datasets',self.data)[0])
    def test_restart_and_consistent_backup(self):
        self.deploy(self.models[0]);before=self.w.predict({'rows':[self.row()]});self.window('missing_labels');self.w.close();again=MlopsWorkspace(self.temp.name,False);after=again.predict({'rows':[self.row()]});self.assertEqual(before['artifact_sha'],after['artifact_sha']);self.assertEqual(before['predictions'],after['predictions']);again.close()
        target=Path(self.temp.name)/'backup.sqlite3'
        with sqlite3.connect(self.w.db) as src,sqlite3.connect(target) as dst:src.backup(dst);self.assertEqual(dst.execute('PRAGMA integrity_check').fetchone()[0],'ok')
    def test_metrics_are_actual_and_without_high_cardinality_labels(self):
        self.deploy(self.models[0]);self.w.predict({'rows':[self.row()]});metric=self.w.metrics().decode();self.assertIn('lab_mlops_requests_total 1.0',metric);self.assertIn('lab_mlops_ready 1',metric);self.assertNotIn(self.models[0],metric);self.assertTrue(metric.endswith('\n'))
    def test_running_train_cancel_never_saves_candidate(self):
        j=self.w.train({'dataset':self.data})['job_id'];worker=threading.Thread(target=self.w.process_one);worker.start()
        for i in range(100):
            if self.w.job(j)['status']=='running':break
            time.sleep(.01)
        self.w.job_action(j,'cancel');worker.join(8);self.assertFalse(worker.is_alive());self.assertEqual(self.w.job(j)['status'],'cancelled');self.assertEqual(len(self.w.state()['models']),2)
    def test_all_invalid_window_rows_keep_null_metrics(self):
        self.deploy(self.models[0]);raw='feature_1,feature_2,feature_3,feature_4,label\n'+','.join(['','','','','1'])+'\n';ds=self.w.import_dataset({'title':'全缺失窗口','kind':'monitoring','text':raw})['dataset_id'];j=self.w.monitor({'dataset':ds,'revision':1})['job_id'];self.w.process_one();self.assertEqual(self.w.job(j)['status'],'succeeded');w=self.w.window(self.w.job(j)['result']['window_id']);self.assertEqual(w['report']['valid_rows'],0);self.assertIsNone(w['report']['accuracy']);self.assertTrue(all(f['psi'] is None for f in w['report']['features']))
    def test_approval_binds_recorded_artifact_sha(self):
        self.approve(self.models[0])
        with self.w.connect(True) as c:c.execute('UPDATE models SET sha=? WHERE id=?',('changed',self.models[0]))
        self.assertEqual(self.w.model(self.models[0])['decision'],'pending')
    def test_optional_mlflow_sync_uses_saved_run_on_retry(self):
        calls=[]
        def remote(path,body=None):
            calls.append((path,body))
            if path=='runs/search':return {'runs':[]}
            if path=='runs/create':return {'run':{'info':{'run_id':'remote-run'}}}
            return {}
        with patch.dict(os.environ,{'LAB_MLFLOW_URL':'http://tracking.invalid'}),patch('shared.mlops_tracking.experiment_id',return_value='7'),patch('shared.mlops_tracking.call',side_effect=remote):
            for i in range(2):j=self.w.track(self.experiments[0])['job_id'];self.w.process_one();self.assertEqual(self.w.job(j)['status'],'succeeded',self.w.job(j))
        self.assertEqual(sum(path=='runs/create' for path,body in calls),1);batch=next(body for path,body in calls if path=='runs/log-batch');self.assertIn('dataset_sha256',[p['key'] for p in batch['params']]);self.assertNotIn('artifact',batch)

if __name__=='__main__':unittest.main()
