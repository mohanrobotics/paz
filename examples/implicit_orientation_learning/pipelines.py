from paz.abstract import SequentialProcessor, Processor
from paz.pipelines import AugmentImage, PreprocessImage
from paz import processors as pr

from processors import MeasureSimilarity
from processors import BlendRandomCroppedBackground
from processors import ConcatenateAlphaMask
from processors import AddOcclusion


class AutoEncoderInference(SequentialProcessor):
    def __init__(self, model):
        super(AutoEncoderInference, self).__init__()
        preprocessing = PreprocessImage(model.input_shape[1:3], None)
        preprocessing.add(pr.ExpandDims(0))
        self.predict = pr.Predict(model, preprocessing)
        self.add(pr.Squeeze(0))
        self.add(pr.DenormalizeImage())
        self.add(pr.CastImage('uint8'))


class ImplicitRotationInference(Processor):
    def __init__(self, encoder, decoder, measure, dictionary):
        super(ImplicitRotationInference, self).__init__()
        preprocessing = PreprocessImage(encoder.input_shape[1:3], None)
        preprocessing.add(pr.ExpandDims(0))
        self.encoder = SequentialProcessor()
        self.encoder.add(pr.Predict(encoder, preprocessing))
        self.encoder.add(MeasureSimilarity(dictionary, measure))

        self.decoder = SequentialProcessor()
        self.decoder.add(pr.Predict(decoder))
        self.decoder.add(pr.Squeeze(0))
        self.decoder.add(pr.DenormalizeImage())
        self.decoder.add(pr.CastImage('uint8'))
        outputs = ['image', 'latent_vector', 'latent_image', 'decoded_image']
        self.wrap = pr.WrapOutput(outputs)

    def call(self, image):
        latent_vector, latent_image = self.encoder(image)
        self.show_image(latent_image)
        decoded_image = self.decoder(latent_vector)
        self.show_image(decoded_image)
        return self.wrap(image, latent_vector, latent_image, decoded_image)


class RandomizeRenderedImage(SequentialProcessor):
    def __init__(self, image_paths, num_occlusions=1, max_radius_scale=0.5):
        super(RandomizeRenderedImage, self).__init__()
        self.add(ConcatenateAlphaMask())
        self.add(BlendRandomCroppedBackground(image_paths))
        for arg in range(num_occlusions):
            self.add(AddOcclusion(max_radius_scale))
        self.add(pr.RandomImageBlur())
        self.add(AugmentImage())


class _DomainRandomization(Processor):
    def __init__(self, renderer, image_paths, num_occlusions, split=pr.TRAIN):
        super(DomainRandomization, self).__init__()
        self.copy = pr.Copy()
        self.render = pr.Render(renderer)
        self.augment = RandomizeRenderedImage(image_paths, num_occlusions)
        preprocessors = [pr.ConvertColorSpace(pr.RGB2BGR), pr.NormalizeImage()]
        self.preprocess = SequentialProcessor(preprocessors)

    def call(self):
        input_image, (matrices, alpha_mask, depth) = self.render()
        label_image = self.copy(input_image)
        if self.split == pr.TRAIN:
            input_image = self.augment(input_image, alpha_mask)
        input_image = self.preprocess(input_image)
        label_image = self.preprocess(label_image)
        return input_image, label_image


class DomainRandomization(SequentialProcessor):
    def __init__(self, renderer, size, image_paths,
                 num_occlusions, split=pr.TRAIN):
        super(_DomainRandomization, self).__init__()
        self.add(DomainRandomization(
            renderer, image_paths, num_occlusions, split))
        self.add(pr.SequenceWrapper(
            {0: {'input_image': [size, size, 3]}},
            {1: {'label_image': [size, size, 3]}}))
