import numpy as np
import tensorflow as tf
import tensorflow.contrib.eager as tfe
from model import EfficientNetB0

# enable eager mode
tf.enable_eager_execution()
tf.set_random_seed(0)
np.random.seed(0)


# Define the loss function
def loss_function(model, x, y, training=True):
	y_ = model(x, training=training)
	loss = tf.losses.softmax_cross_entropy(y, y_)
	print(loss)
	return loss

# Prints the number of parameters of a model
def get_params(model):
	total_parameters = 0
	for variable in model.variables:
		# shape is an array of tf.Dimension
		shape = variable.get_shape()
		variable_parameters = 1

		for dim in shape:
			variable_parameters *= dim.value
		total_parameters += variable_parameters
	print("Total parameters of the net: " + str(total_parameters)+ " == " + str(total_parameters/1000000.0) + "M")

# Returns a pretrained model (can be used in eager execution)
def get_pretrained_model(num_classes, input_shape=(224, 224, 3)):
	model = tf.keras.applications.ResNet50(input_shape=input_shape, include_top=False, weights='imagenet')
	logits = tf.keras.layers.Dense(num_classes, name='fc')(model.output)
	model = tf.keras.models.Model(model.inputs, logits)
	return model
		
# Writes a summary given a tensor
def write_summary(tensor, writer, name):
	with tf.contrib.summary.always_record_summaries(): # record_summaries_every_n_global_steps(1)
		writer.set_as_default()
		tf.contrib.summary.scalar(name, tensor)


# Trains the model for certains epochs on a dataset
def train(dset_train, dset_test, model, epochs=5, show_loss=False):
	# Define summary writers and global step for logging
	writer_train = tf.contrib.summary.create_file_writer('./logs/train')
	writer_test = tf.contrib.summary.create_file_writer('./logs/test')
	global_step=tf.train.get_or_create_global_step()  # return global step var

	for epoch in range(epochs):
		print('epoch: '+ str(epoch))
		for x, y in dset_train: # for every batch
			global_step.assign_add(1) # add one step per iteration

			with tf.GradientTape() as g:
				y_ = model(x, training=True)
				loss = tf.losses.softmax_cross_entropy(y, y_)
				print ("loss", loss)
				write_summary(loss, writer_train, 'loss')
				if show_loss: print('Training loss: ' + str(loss.numpy()))

			# Gets gradients and applies them
			grads = g.gradient(loss, model.variables)
			optimizer.apply_gradients(zip(grads, model.variables))

		# Get accuracies
		train_acc = get_accuracy(dset_train, model, training=True)
		test_acc = get_accuracy(dset_test, model, writer=writer_test)
		# write summaries and print
		write_summary(train_acc, writer_train, 'accuracy')
		write_summary(test_acc, writer_test, 'accuracy')
		print('Train accuracy: ' + str(train_acc.numpy()))
		print('Test accuracy: ' + str(test_acc.numpy()))


# Tests the model on a dataset
def get_accuracy(dset_test, model, training=False,  writer=None):
	accuracy = tfe.metrics.Accuracy()
	if writer: loss = [0, 0]

	for x, y in dset_test: # for every batch
		y_ = model(x, training=training)
		accuracy(tf.argmax(y, 1), tf.argmax(y_, 1))

		if writer: 
			loss[0] += tf.losses.softmax_cross_entropy(y, y_)
			loss[1] += 1.

	if writer:
		write_summary(tf.convert_to_tensor(loss[0]/loss[1]), writer, 'loss')

	return accuracy.result()


def restore_state(saver, checkpoint):
	try:
		saver.restore(checkpoint)
		print('Model loaded')
	except Exception:
		print('Model not loaded')


def init_model(model, input_shape):
	model._set_inputs(np.zeros(input_shape))

if __name__ == "__main__":


	# constants
	image_size = 28
	batch_size = 8192
	epochs = 100
	num_classes = 10
	channels= 1

	# Get dataset
	(x_train, y_train), (x_test, y_test) = tf.keras.datasets.mnist.load_data()

	# Reshape images
	x_train = x_train.reshape(-1, image_size, image_size, channels).astype('float32')
	x_test = x_test.reshape(-1, image_size, image_size, channels).astype('float32')

	# We are normalizing the images to the range of [-1, 1]
	x_train = x_train / 127.5 - 1
	x_test = x_test / 127.5 - 1

	# Onehot: from 28,28 to 28,28,n_classes
	y_train_ohe = tf.one_hot(y_train, depth=num_classes).numpy()
	y_test_ohe = tf.one_hot(y_test, depth=num_classes).numpy()


	print('x train', x_train.shape)
	print('y train', y_train_ohe.shape)
	print('x test', x_test.shape)
	print('y test', y_test_ohe.shape)

	# Creates the tf.Dataset
	n_elements_train = x_train.shape[0]
	n_elements_test = x_test.shape[0]
	dset_train = tf.data.Dataset.from_tensor_slices((x_train, y_train_ohe)).shuffle(n_elements_train).batch(batch_size)
	dset_test = tf.data.Dataset.from_tensor_slices((x_test, y_test_ohe)).shuffle(n_elements_test).batch(batch_size)

	model = EfficientNetB0(classes=10, input_shape=(None, image_size, image_size, channels))

 	# optimizer
	optimizer = tf.train.AdamOptimizer(0.001)


	# show the number of parametrs of the model
	get_params(model)

	# Init saver 
	saver_model = tfe.Saver(var_list=model.variables) # can use also ckpt = tfe.Checkpoint(model=model) 

	restore_state(saver_model, 'weights/last_saver')

	train(dset_train=dset_train, dset_test=dset_test, model=model, epochs=epochs)
	
	saver_model.save('weights/last_saver')


