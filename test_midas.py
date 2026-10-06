import unittest
from datetime import date, datetime, timezone

from midas_core.application.analysis import build_report as report
from midas_core.domain.features import feature_vector, latest_features, month_end_series
from midas_core.domain.regression import rank_correlation, temporal_partitions, temporal_split
from midas_core.training import VariableTrainer

def month(value):
    return datetime(2020 + value // 12, value % 12 + 1, 1, tzinfo=timezone.utc)

class ValidationTests(unittest.TestCase):
    def test_training_labels_precede_test_dates(self):
        rows=[{'as_of':month(0),'label_end':month(1)},
              {'as_of':month(1),'label_end':month(4)},
              {'as_of':month(2),'label_end':month(5)}]
        train,test=temporal_split(rows,month(2))
        self.assertEqual(train,[rows[0]])
        self.assertEqual(test,[rows[2]])
        self.assertLess(max(r['label_end'] for r in train),min(r['as_of'] for r in test))

    def test_three_way_partition_expunges_crossing_labels(self):
        rows=[{'as_of':month(index),'label_end':month(index+3)} for index in range(30)]
        parts=temporal_partitions(rows)
        self.assertLess(max(row['label_end'] for row in parts.selection_train),parts.validation_start)
        self.assertLess(max(row['label_end'] for row in parts.evaluation_train),parts.test_start)
        self.assertTrue(all(parts.validation_start <= row['as_of'] < parts.test_start for row in parts.validation))
        self.assertTrue(all(row['label_end'] < parts.test_start for row in parts.validation))
        self.assertTrue(all(row['as_of'] >= parts.test_start for row in parts.test))

    def test_rank_correlation_rewards_correct_order(self):
        instant=month(0)
        rows=[{'as_of':instant} for _ in range(4)]
        self.assertAlmostEqual(rank_correlation(rows,[1,2,3,4],[10,20,30,40]),1.0)
        self.assertAlmostEqual(rank_correlation(rows,[1,2,3,4],[40,30,20,10]),-1.0)

    def test_features_do_not_read_future_values(self):
        values=[100+i for i in range(15)]
        expected=feature_vector(values,12)
        values[13:]=[1,10000]
        self.assertEqual(expected,feature_vector(values,12))

    def test_monthly_series_uses_last_available_adjusted_close(self):
        rows=[
            {'price_date':date(2024,1,2),'close':10,'adjusted_close':9},
            {'price_date':date(2024,1,31),'close':12,'adjusted_close':11},
            {'price_date':date(2024,2,28),'close':13,'adjusted_close':None},
        ]
        series=month_end_series(rows)
        self.assertEqual([value for _,value in series],[11.0,13.0])
        self.assertIsNone(latest_features(series))

    def test_invalid_horizon_rejected_before_query(self):
        with self.assertRaises(ValueError): report(1)

class VariableTrainerTests(unittest.TestCase):
    def make_rows(self):
        rows=[]
        for index in range(50):
            for asset in range(4):
                momentum=(index-20)/100 + asset/50
                features={
                    'momentum_6m':momentum,
                    'momentum_12m':momentum*1.2,
                    'volatility':0.15+asset*0.04,
                    'drawdown':-0.25+asset*0.05,
                    'rsi_14m':50.0+momentum*20,
                    'macd_signal':momentum*0.5,
                    'sma_ratio_12m':1.0+momentum*0.1,
                    'bb_position':0.5+momentum*0.2,
                    'atr_ratio':0.05+asset*0.01,
                    'pe_ratio':15.0+asset*2,
                    'dividend_yield':0.03+asset*0.01,
                    'net_margin':0.10+asset*0.02,
                    'adx_14m':25.0+momentum*10,
                    'stochastic_k':50.0+momentum*20,
                    'williams_r':-50.0+momentum*20,
                    'obv_slope':momentum*0.5,
                    'mfi_14m':50.0+momentum*15,
                }
                rows.append({
                    'ticker':f'TEST{asset}',
                    'as_of':month(index),
                    'label_end':month(index+3),
                    'features':features,
                    'target':0.03+momentum*0.7-asset*0.01,
                })
        return rows

    def test_trainer_returns_model_metrics_and_selected_variables(self):
        result=VariableTrainer().train(self.make_rows(),now=month(60))
        self.assertEqual(result.parameters['model_version'],5)
        self.assertEqual(result.parameters['features'],
            ['momentum_6m','momentum_12m','volatility','drawdown','rsi_14m','macd_signal','sma_ratio_12m','bb_position','atr_ratio','pe_ratio','dividend_yield','net_margin','adx_14m','stochastic_k','williams_r','obv_slope','mfi_14m'])
        self.assertIn('algorithm',result.parameters)
        self.assertIn('selection_results',result.parameters)
        self.assertGreater(len(result.parameters['selection_results']),1)
        self.assertEqual(len(result.model.weights),18)
        self.assertGreater(result.metrics['test'],0)
        self.assertIn('rank_correlation',result.metrics)

    def test_trainer_rejects_missing_variable(self):
        rows=self.make_rows()
        del rows[0]['features']['drawdown']
        with self.assertRaisesRegex(ValueError,'Variavel ausente: drawdown'):
            VariableTrainer().train(rows,now=month(60))

if __name__=='__main__': unittest.main()
