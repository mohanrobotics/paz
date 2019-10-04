import numpy as np
import types


class Processor(object):
    """ Abstract class for creating a new processor unit.
    A processor unit logic lives in method `call` which is wrapped
    to work in two different modes: stochastic and deterministic.
    The stochastic mode is activated whenever a value different than
    `None` is given to the variable `probability`.
    If `None` is passed to `probability` the processor unit works
    deterministically.
    If the processor unit is working stochastically the logic in the
    method `call` will be applied to the input with the
    probability value given.
    It the processor is working deterministically the logic of the
    method `call` will be always applied.

    # Arguments
        probability: None or float between [0, 1]. See above for description.
        name: String indicating name of the processing unit.

    # Methods
        call()
    """
    def __init__(self, probability=None, name=None):
        self.probability = probability
        self.name = name

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        if name is None:
            name = self.__class__.__name__
        self._name = name

    @property
    def probability(self):
        return self._probability

    @probability.setter
    def probability(self, probability):
        if probability is None:
            self._probability = None
            self._process = self.call
        elif (0.0 <= probability <= 1.0):
            self._probability = probability
            self._process = self.stochastic_process
        else:
            raise ValueError('Probability has to be between [0, 1]')

    def stochastic_process(self, kwargs):
        if np.random.random() < self.probability:
            kwargs = self.call(kwargs)
        return kwargs

    def call(self, kwargs):
        """ Logic to be implemented to transform kwargs
        """
        raise NotImplementedError

    def __call__(self, kwargs):
        return self._process(kwargs)


class InputProcessor(Processor):
    """ Input processor used as first process to any SequentialProcessor.
    """
    def __init__(self):
        super(InputProcessor, self).__init__()

    def __call__(self, **kwargs):
        return kwargs


class SequentialProcessor(object):
    """ Abstract class for creating a sequential pipeline of processors.
    # Methods:
        add()
    """
    def __init__(self):
        self.processors = [InputProcessor()]

    def add(self, processor):
        """ Adds a process to the sequence of processes to be applied to input.
        # Arguments
            processor: An extended class of the parent class `Process`.
        """
        self.processors.append(processor)

    def __call__(self, **kwargs):
        kwargs = self.processors[0](**kwargs)
        for processor in self.processors[1:]:
            kwargs = processor(kwargs)
        return kwargs


class LambdaProcessor(object):
    """Applies a lambda function as a processor transformation.
    # Arguments
        lambda_function: A lambda function.
    """

    def __init__(self, lambda_function):
        assert isinstance(lambda_function, types.LambdaType)
        self.lambda_function = lambda_function

    def __call__(self, kwargs):
        return self.lambda_function(kwargs)