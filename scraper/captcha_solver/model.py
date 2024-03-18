from mltu.inferenceModel import OnnxInferenceModel
from mltu.utils.text_utils import ctc_decoder

from mltu.configs import BaseModelConfigs

import cv2
import numpy as np

import os
from pathlib import Path

import threading

from typing import Union, Optional


current_file = __file__


class CaptchaSolver(OnnxInferenceModel):
	def __init__(self, model_path: str, char_list: Union[str, list], *args, **kwargs):
		super().__init__(model_path=model_path, *args, **kwargs)
		self._char_list = char_list
		self._thread_lock = threading.Lock()

	@classmethod
	def load(cls) -> 'CaptchaSolver':
		model_path = os.path.join(Path(current_file).parent, 'model_cfg')
		model_configs = BaseModelConfigs.load(os.path.join(model_path, 'configs.yaml'))
		return cls(model_path=model_path, char_list=model_configs.vocab)

	def predict(self, img: np.ndarray) -> str:
		img = cv2.resize(img, self.input_shape[:2][::-1])
		img_pred = np.expand_dims(img, axis=0).astype(np.float32)
		preds = self.model.run(None, {self.input_name: img_pred})[0]

		text = ctc_decoder(preds, self._char_list)[0]
		return text

	def solve_captcha(self, captcha_img: Optional[bytes] = None, captcha_img_path: Optional[str] = None) -> str:
		with self._thread_lock:
			if captcha_img and captcha_img_path:
				raise ValueError('Got both image and image path')
			elif not captcha_img and not captcha_img_path:
				raise ValueError('Expecting image or image path, got neither')

			if captcha_img:
				nparr = np.frombuffer(captcha_img, np.uint8)
				captcha_img_ndarray = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
			elif captcha_img_path:
				captcha_img_ndarray = cv2.imread(captcha_img_path)

			return self.predict(img=captcha_img_ndarray)
