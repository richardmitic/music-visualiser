import pyglet
from pyglet.gl import *
from pyglet import clock
from pyglet.window import key
from scipy.signal import hilbert
import numpy as np
import pyaudio
import math
import pylab
import cmath



### Parameters for creating the World ###
my_audio_params = (	pyaudio.paInt16, 1, 44100, True, False, 1024 )
WIDTH = 600
HEIGHT = 600
FPS = 100


### Class definitons ###
class World(pyglet.window.Window):
	def __init__(self, w, h, fps, audio_params):
		if w and h and fps > 0:
			pyglet.clock.schedule_interval(self.update, 1/float(fps))
			super(World, self).__init__(width=w, height=h)
			self.clear()
		else:
			raise Exception('Invalid width, height or fps')		
		self.display_mode = 1	# 1: Just hilbert
								# 2: Just waveform
								# 3: Both
		pyglet.clock.set_fps_limit(fps)
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)                             
		glEnable(GL_BLEND)                                                            
		glEnable(GL_LINE_SMOOTH)                                                     
		glLineWidth(2)
		self.time = 0.
		self.last_text = None
		self.text = None
		self.audio_params = audio_params
		self.line_points = np.zeros(self.audio_params[5]*2)
		self.line_colour = (0.5, 0.5, 0.5, 0.8)
		self.wave_display = np.zeros(self.audio_params[5])
		self.scale = 0.04
		self.hold = False
		self.fade_time = 10.
		self.f = Slide_filter(50)
		self.ss = Screenshot_saver()
		self.p = pyaudio.PyAudio()
		self.stream = self.p.open(	format = self.audio_params[0],
		                			channels = self.audio_params[1],
		                			rate = self.audio_params[2],
		                			input = self.audio_params[3],
		                			output = self.audio_params[4],
		                			frames_per_buffer = self.audio_params[5])

	def put_text(self,string):
		self.text = string
		self.last_text = self.time

	def on_draw(self):
		if self.hold == False:
			pyglet.gl.glColor4f(0.,0.,0.,0.1)
			w = self.width
			h = self.height
			glLineWidth(2)
			pyglet.graphics.draw(4, pyglet.gl.GL_POLYGON,('v2i', (0,0,0,h,w,h,w,0)))
			if self.display_mode in [1,3]:
				r,g,b = self.line_colour
				pyglet.gl.glColor4f(r,g,b,0.8)
				pyglet.graphics.draw(len(self.line_points)/2, pyglet.gl.GL_LINE_STRIP, ('v2f', self.line_points))
			if self.display_mode in [2,3]:
				pyglet.gl.glColor4f(0.,1.,0.,0.8)
				pyglet.graphics.draw(len(self.wave_display)/2, pyglet.gl.GL_LINE_STRIP, ('v2f', self.wave_display))
			if self.text:
				if self.time-self.last_text < 1:
					pyglet.text.Label(self.text, bold=True, font_size=14, color=(200,200,200,100), x=10, y=10).draw()
	
	def get_audio(self):
		try:
			raw = self.stream.read(self.audio_params[5])
		except IOError as ex:
			if ex[1] != pyaudio.paInputOverflowed:
				raise
			else:
				print "Warning: audio input buffer overflow"
				pass
			raw = '\x00' * self.audio_params[5]
		return np.array(np.frombuffer(raw,np.int16), dtype=np.float64)
		
	
	def update(self,dt):
		audio = self.get_audio()
		self.line_colour = interp_colour(rms(audio/10000.))
		shifted = hilbert(audio)*self.scale
		shifted = np.add(shifted, self.width/2+(self.height/2)*1j)
		shifted = self.f.filter(shifted)
		for i, co_ord in enumerate(shifted):	
			self.line_points[2*i] = co_ord.real
			self.line_points[(2*i)+1] = co_ord.imag
		wave_offset_y = self.height*0.5*(1-math.sqrt(2)) # To account for the 200+200j added earlier
		wave_offset_x = (self.width - len(shifted)/2)/2
		for i, co_ord in enumerate(shifted[::2]):
			self.wave_display[2*i] = i + wave_offset_x
			self.wave_display[(2*i)+1] = abs(co_ord) + wave_offset_y
		self.on_draw()
		self.time += dt
		#print self.time
	
	def on_key_press(self,symbol,modifiers):
		if symbol == key.Q:
			my_world.f.a = max(1., my_world.f.a*1.2)
			self.put_text("Filtering value: "+str(my_world.f.a))
		elif symbol == key.A:
			my_world.f.a = max(1., my_world.f.a/1.2)
			self.put_text("Filtering value: "+str(my_world.f.a))
		elif symbol == key.W:
			my_world.scale += 0.002
			self.put_text("Scale: "+str(my_world.scale))
		elif symbol == key.S:
			my_world.scale -= 0.002
			self.put_text("Scale: "+str(my_world.scale))
		if symbol == key.SPACE:
			my_world.hold = not my_world.hold
		if symbol == key.P:
			self.put_text(self.ss.save_image())
			self.last_text = self.time+3 # Account for the time taken to save the file
			self.hold = False
		if symbol == key.Z:
			if self.display_mode < 3:
				self.display_mode += 1
			else:
				self.display_mode = 1

		
class Slide_filter():
	def __init__(self, a):
		self.buffer = np.zeros(2, dtype='complex128')
		self.a = a

	def filter(self, input_buff):
		b = np.zeros(len(input_buff), dtype='complex128')
		for i in range(len(input_buff)):
			self.buffer[1] = self.buffer[0]
			self.buffer[0] = self.buffer[1] + ((input_buff[i]-self.buffer[1]) / self.a)
			b[i] = self.buffer[0]
		return b


class Screenshot_saver():
	def __init__(self):
		self.m = pyglet.image.get_buffer_manager()
		import os
		if not os.path.exists('screenshots'):
			os.mkdir('screenshots')
	
	def save_image(self):
		from datetime import datetime
		img = self.m.get_color_buffer().get_image_data()
		img.format = 'RGB'
		d = datetime.now().strftime("_%I.%M.%S_%d-%m-%Y")
		filepath = 'screenshots/image'+d+'.png'
		try:
			img.save(filepath)
			return str(filepath)+" saved"
		except:
			return "Screenshot could not be saved"


### Miscellaneous function definitions ###
def rms(buff):
	rms_val = math.sqrt(sum(np.multiply(buff,buff))/len(buff))
	return rms_val
	
def interp_colour(pos):
	c =	[(14, 82 , 127), # blue
		( 69, 138, 44 ), # green
		(208, 203, 57 ), # yellow
		(196, 28 , 28)]  # red
	f = np.divide(c,255.)
	sector1 = max(min((pos*len(f))-0.5, float(len(f)-1)), 0.)
	sector2 = max(min((pos*len(f))+0.5, float(len(f)-1)), 0.)
	f1 = f[int(sector1)]
	f2 = f[int(sector2)]
	blend = sector1 - int(sector1)
	return (f2*blend) + (f1*(1.-blend))



### --- MAIN CODE --- ###
my_world = World(WIDTH, HEIGHT, FPS, my_audio_params)
pyglet.app.run()