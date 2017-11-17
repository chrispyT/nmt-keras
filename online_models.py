import logging
from keras.layers import Input, Lambda
from keras.models import Model
from keras.optimizers import *
from keras.losses import *

logging.basicConfig(level=logging.DEBUG, format='[%(asctime)s] %(message)s', datefmt='%d/%m/%Y %H:%M:%S')


def setOptimizer(params):
    """
    Sets and compiles a new optimizer for the Translation_Model.
    :param params: Dictionary with optimizer parameters
    :return: Compiled Keras optimizer
    """
    if params.get('VERBOSE', 0) > 0:
        logging.info("Preparing optimizer: %s [LR: %s - LOSS: %s - "
                     "CLIP_C %s - CLIP_V  %s - LR_OPTIMIZER_DECAY %s] and compiling." %
                     (str(params['OPTIMIZER']),
                      str(params.get('LR', 0.01)),
                      str(params.get('LOSS', 'categorical_crossentropy')),
                      str(params.get('CLIP_C', 0.)),
                      str(params.get('CLIP_V', 0.)),
                      str(params.get('LR_OPTIMIZER_DECAY', 0.0))
                      ))

    if params['OPTIMIZER'].lower() == 'sgd':
        optimizer = SGD(lr=params.get('LR', 0.01),
                        momentum=params.get('MOMENTUM', 0.0),
                        decay=params.get('LR_OPTIMIZER_DECAY', 0.0),
                        nesterov=params.get('NESTEROV_MOMENTUM', False),
                        clipnorm=params.get('CLIP_C', 10.),
                        clipvalue=params.get('CLIP_V', 0.), )

    elif params['OPTIMIZER'].lower() == 'rsmprop':
        optimizer = RMSprop(lr=params.get('LR', 0.001),
                            rho=params.get('RHO', 0.9),
                            decay=params.get('LR_OPTIMIZER_DECAY', 0.0),
                            clipnorm=params.get('CLIP_C', 10.),
                            clipvalue=params.get('CLIP_V', 0.))

    elif params['OPTIMIZER'].lower() == 'adagrad':
        optimizer = Adagrad(lr=params.get('LR', 0.01),
                            decay=params.get('LR_OPTIMIZER_DECAY', 0.0),
                            clipnorm=params.get('CLIP_C', 10.),
                            clipvalue=params.get('CLIP_V', 0.))

    elif params['OPTIMIZER'].lower() == 'adadelta':
        optimizer = Adadelta(lr=params.get('LR', 1.0),
                             rho=params.get('RHO', 0.9),
                             decay=params.get('LR_OPTIMIZER_DECAY', 0.0),
                             clipnorm=params.get('CLIP_C', 10.),
                             clipvalue=params.get('CLIP_V', 0.))

    elif params['OPTIMIZER'].lower() == 'adam':
        optimizer = Adam(lr=params.get('LR', 0.001),
                         beta_1=params.get('BETA_1', 0.9),
                         beta_2=params.get('BETA_2', 0.999),
                         decay=params.get('LR_OPTIMIZER_DECAY', 0.0),
                         clipnorm=params.get('CLIP_C', 10.),
                         clipvalue=params.get('CLIP_V', 0.))

    elif params['OPTIMIZER'].lower() == 'adamax':
        optimizer = Adamax(lr=params.get('LR', 0.002),
                           beta_1=params.get('BETA_1', 0.9),
                           beta_2=params.get('BETA_2', 0.999),
                           decay=params.get('LR_OPTIMIZER_DECAY', 0.0),
                           clipnorm=params.get('CLIP_C', 10.),
                           clipvalue=params.get('CLIP_V', 0.))

    elif params['OPTIMIZER'].lower() == 'nadam':
        optimizer = Nadam(lr=params.get('LR', 0.002),
                          beta_1=params.get('BETA_1', 0.9),
                          beta_2=params.get('BETA_2', 0.999),
                          schedule_decay=params.get('LR_OPTIMIZER_DECAY', 0.0),
                          clipnorm=params.get('CLIP_C', 10.),
                          clipvalue=params.get('CLIP_V', 0.))

    elif 'pas' in params['OPTIMIZER'].lower():
        optimizer = eval(params['OPTIMIZER'])(params.get('WEIGHT_SHAPES', None),
                                              lr=params['LR'],
                                              c=params['C'],
                                              clipnorm=params.get('CLIP_C', 10.),
                                              clipvalue=params.get('CLIP_V', 0.))
    else:
        logging.error('\tNot supported optimizer!')

    return optimizer


def build_online_models(models, params):
    trainer_models = []
    if params['USE_CUSTOM_LOSS']:
        logging.info('Using custom loss.')
        # Add additional input layer to models in order to train with custom loss function
        for nmt_model in models:
            nmt_model.setParams(params)
            if params['LOSS'] == 'log_diff':
                x = Input(name="x", batch_shape=tuple([None, None]))
                hyp = Input(name="hyp", batch_shape=tuple([None, None, None]))
                yref = Input(name="yref", batch_shape=tuple([None, None, None]))
                state_below_h = Input(name="state_below_h", batch_shape=tuple([None, None]))
                preds_y = nmt_model.model.outputs[0]
                preds_h = nmt_model.model([nmt_model.model.inputs[0], state_below_h])
                loss_out = Lambda(eval(params['LOSS']),
                                  output_shape=(1,),
                                  name=params['LOSS'],
                                  supports_masking=False)([yref, preds_y, hyp, preds_h])
                trainer_model = Model(inputs=nmt_model.model.inputs + [state_below_h, yref, hyp],
                                      outputs=loss_out)

            elif params['LOSS'] == 'weighted_log_diff':
                hyp = Input(name="hyp", batch_shape=tuple([None, None, None]))
                yref = Input(name="yref", batch_shape=tuple([None, None, None]))
                state_below_h = Input(name="state_below_h", batch_shape=tuple([None, None]))
                preds_h = nmt_model.model([nmt_model.model.inputs[0], state_below_h])
                preds_y = nmt_model.model.outputs[0]
                weight = Input(name="weight", batch_shape=tuple([None, 1]))
                loss_out = Lambda(eval(params['LOSS']),
                                  output_shape=(1,),
                                  name=params['LOSS'],
                                  supports_masking=False)([yref, preds_y, hyp, preds_h, weight])
                trainer_model = Model(inputs=nmt_model.model.inputs + [state_below_h, weight] + [yref, hyp],
                                      outputs=loss_out)

            elif params['LOSS'] == 'log_diff_plus_categorical_crossentropy':
                hyp1 = Input(name="hyp1", batch_shape=tuple([None, None, None]))
                hyp2 = Input(name="hyp2", batch_shape=tuple([None, None, None]))
                yref = Input(name="yref", batch_shape=tuple([None, None, None]))
                state_below_h1 = Input(name="state_below_h1", batch_shape=tuple([None, None]))
                state_below_h2 = Input(name="state_below_h2", batch_shape=tuple([None, None]))
                preds_h1 = nmt_model.model([nmt_model.model.inputs[0], state_below_h1])
                preds_h2 = nmt_model.model([nmt_model.model.inputs[0], state_below_h2])
                preds_y = nmt_model.model.outputs[0]
                weight = Input(name="weight", batch_shape=tuple([None, 1]))
                loss_out = Lambda(eval(params['LOSS']),
                                  output_shape=(1,),
                                  name=params['LOSS'],
                                  supports_masking=False)([yref, preds_y, hyp1, preds_h1, hyp2, preds_h2, weight])

                trainer_model = Model(
                    inputs=nmt_model.model.inputs + [state_below_h1, state_below_h2, weight] + [yref, hyp1, hyp2],
                    outputs=loss_out)

            elif params['LOSS'] == 'linear_interpolation_categorical_crossentropy':
                metric_value = Input(name="metric_value", batch_shape=tuple([None, 1]))
                weight = Input(name="weight", batch_shape=tuple([None, 1]))
                yref = Input(name="yref", batch_shape=tuple([None, None, None]))
                preds_y = nmt_model.model.outputs[0]
                loss_out = Lambda(eval(params['LOSS']),
                                  output_shape=(None,),
                                  name=params['LOSS'],
                                  supports_masking=False)([yref, preds_y, metric_value, weight])
                trainer_model = Model(inputs=nmt_model.model.inputs + [yref, metric_value, weight],
                                      outputs=loss_out)

            elif params['LOSS'] == 'hybrid_log_diff':
                state_below_h1 = Input(name="state_below_h1", batch_shape=tuple([None, None]))
                preds_h1 = nmt_model.model([nmt_model.model.inputs[0], state_below_h1])
                hyp1 = Input(name="hyp1", batch_shape=tuple([None, None, None]))
                yref = Input(name="yref", batch_shape=tuple([None, None, None]))
                preds_y = nmt_model.model.outputs[0]

                constant = Input(name="p_ty", batch_shape=tuple([None, 1]))
                weight1 = Input(name="weight1", batch_shape=tuple([None, 1]))
                weight2 = Input(name="weight2", batch_shape=tuple([None, 1]))
                inputs = [yref, preds_y, hyp1, preds_h1, weight1, weight2, constant]

                loss_out = Lambda(eval(params['LOSS']),
                                  output_shape=(None,),
                                  name=params['LOSS'],
                                  supports_masking=False)(inputs)
                trainer_model = Model(inputs=nmt_model.model.inputs + [state_below_h1] + [yref, hyp1, weight1,
                                                                                          weight2, constant],
                                      outputs=loss_out)


            elif isinstance(params['LOSS'], list):
                raise NotImplementedError, 'WIP!'
                state_below_h1 = Input(name="state_below_h1", batch_shape=tuple([None, None]))
                preds_h1 = nmt_model.model([nmt_model.model.inputs[0], state_below_h1])
                yref = Input(name="yref", batch_shape=tuple([None, None, None]))
                preds_y = nmt_model.model.outputs[0]
                inputs = [yref, preds_y, hyp1, preds_h1, weight1, weight2]
                losses = [Lambda(eval(loss), output_shape=(None,),
                                 name=loss, supports_masking=False)(inputs) for loss in params['LOSS']]

                trainer_model = Model(inputs=nmt_model.model.inputs + [state_below_h1] + [yref, weight1, weight2],
                                      outputs=loss_out)

            trainer_models.append(trainer_model)
            # Set custom optimizer
            weights = trainer_model.trainable_weights
            # Weights from Keras 2 are already (topologically) sorted!
            if not weights:
                logging.warning("You don't have any trainable weight!!")
            params['WEIGHT_SHAPES'] = [(w.name, K.get_variable_shape(w)) for w in weights]

            if isinstance(params['LOSS'], str):
                params['LOSS'] = {params['LOSS']: lambda y_true, y_pred: y_pred}
            elif isinstance(params['LOSS'], list):
                params['LOSS'] = [{loss_name: lambda y_true, y_pred: y_pred} for loss_name in params['LOSS']]
                if params.get('LOSS_WEIGHTS') is None:
                    logging.warning('Loss weights not given! Using the same weight for each loss')
                    params['LOSS_WEIGHTS'] = [1./len(params['LOSS']) for _ in params['LOSS']]
                else:
                    assert len(params['LOSS_WEIGHTS']) == len(params['LOSS']), 'You should provide a weight' \
                                                                               'for each loss!'

            optimizer = setOptimizer(params)
            trainer_model.compile(loss=params['LOSS'],
                                  optimizer=optimizer,
                                  loss_weights=params.get('LOSS_WEIGHTS', None),
                                  #  As this is online training, we probably won't need sample_weight
                                  sample_weight_mode=None,  # 'temporal' if params['SAMPLE_WEIGHTS'] else None,
                                  metrics=params.get('KERAS_METRICS', []))
        return trainer_models
    else:
        for nmt_model in models:
            nmt_model.setParams(params)
            nmt_model.setOptimizer()
        return models
