#!/usr/bin/env python
"""
Asteroids-inspired laser projector game for the Ether Dream DAC.

Copyright (c) 2012
Brandon Thomas <echelon@gmail.com>
http://possibilistic.org
https://github.com/echelon
"""

# STDLIB
import getopt
import math
import random
import itertools
import sys
import thread
import time
from datetime import datetime, timedelta

# PYGAME
import pygame

# MY CODES
from daclib import dac
from daclib.common import *
from globalvals import *
from colors import *
from entities.ship import *
from entities.healthbar import *
from entities.asteroid import *
from entities.particle import *
from entities.bullet import *
from entities.score import *
from pointstream import PointStream
from controller import setup_controls

import sim

"""
Main Program
"""

DRAW = None # Will be the global PointStream
bulletSpawnOk = True
pygame.init()

pygame.mixer.get_init() 
pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=4096)
pew = pygame.mixer.Sound('pew.ogg')
exp = pygame.mixer.Sound('explode.wav')

pygame.display.init()
class GameState(object):
	"""
	A simple structure to keep track of 'global' game state.
	"""
	def __init__(self):
		# Objects
		self.ship = None
		self.healthbar = None
		self.bullets = []
		self.asteroids = []
		self.gameOver = False

STATE = GameState()

class Player(object):
	"""
	Player (conflated)
		- Contain joystick ref
		- Contain visual object
	"""
	def __init__(self, joystick, radius=BALL_RADIUS,
			rgb=(CMAX, CMAX, CMAX)):
		self.js = joystick
		self.score = 0
		self.pid = 0

		# Joystick
		joystick.init()

		# debug
		numButtons = joystick.get_numbuttons()
		print joystick.get_name()
		print joystick.get_numaxes()
		print numButtons

	def __str__(self):
		return self.js.get_name()

"""
THREADS
"""

ps = PointStream()
DRAW = ps

simulator = sim.SIM()

def dac_thread(load_sim):
	global PLAYERS, DRAW

	while True:
		try:
			if load_sim == 0:
				d = dac.DAC(dac.find_first_dac())
				d.play_stream(ps)
			else:
				simulator.play_stream(ps)

		except Exception as e:

			import sys, traceback
			print '\n---------------------'
			print 'Exception: %s' % e
			print '- - - - - - - - - - -'
			traceback.print_tb(sys.exc_info()[2])
			print "\n"
			pass


def joystick_thread():
	"""Manage the joysticks with PyGame"""
	global PLAYERS
	global bulletSpawnOk

	pygame.joystick.init()

	# Wait until we have a joystick
	# TODO: Doesn't account for unplugged. 
	while not pygame.joystick.get_count():
		print "No Joystick detected!"
		time.sleep(5)

	# This loop will avoid trying to initialize any disconnected controllers (such as wii-mote)
	initjoy = -1
	for iX in range(0, pygame.joystick.get_count()):
		js = pygame.joystick.Joystick(iX)
		js.init()
		if js.get_numaxes() > 0:
			initjoy = js
			print "Joystick #%i %s axis=%s btn=%s" % (iX,  js.get_name(), js.get_numaxes(), js.get_numbuttons())
			break

	p1 = Player(initjoy, rgb = COLOR_PINK)

	PLAYERS.append(p1)

	numButtons = p1.js.get_numbuttons() # XXX NO!
	bulletLastFired = datetime.now()

	# Controller wrapper (Xbox, PS3, etc.)
	controller = setup_controls(p1.js)

	# Bullet color increment
	colors = [COLOR_GREEN, COLOR_RED, COLOR_BLUE, COLOR_YELLOW]
	ship = STATE.ship
	ci = 0

	while True:
		e = pygame.event.get()

		for p in PLAYERS:
			lVert, lHori, rVert, rHori = (0, 0, 0, 0)

			lVert = controller.getLeftVert()
			lHori = controller.getLeftHori()
			rVert = controller.getRightVert()
			rHori = controller.getRightHori()

			if abs(rVert) > 0.2:
				y = ship.y
				y += -1 * int(rVert * SIMPLE_TRANSLATION_SPD)
				if MIN_Y < y < MAX_Y:
					ship.y = y

			if abs(rHori) > 0.2:
				x = ship.x
				x += -1 * int(rHori * SIMPLE_TRANSLATION_SPD)
				if MIN_X < x < MAX_X:
					ship.x = x

			# Player rotation
			t = math.atan2(lVert, lHori)
			ship.theta = t

			# Health Bar Location
			STATE.healthbar.x = ship.x
			STATE.healthbar.y = ship.y - 2500

			# Both triggers shoot
			tOff = [0.0, -1.0]
			trigger = True

			if controller.getLeftTrigger() in tOff and \
					controller.getRightTrigger() in tOff:
				trigger = False

			if bulletSpawnOk and trigger:
				td = timedelta(milliseconds=150) # TODO: Cache this.
				if datetime.now() > bulletLastFired + td:
					ang = ship.theta + math.pi

					ci = (ci+1) % len(colors)
					color = colors[ci]
					b = Bullet(ship.x, ship.y, rgb=color, shotAngle=ang)
					DRAW.objects.append(b)
					STATE.bullets.append(b)
					bulletLastFired = datetime.now()
					ch = pew.play()

		time.sleep(0.02) # Keep this thread from hogging CPU


numEnemies = 0 # XXX: MOve to game state object... 
numBullets = 0 # XXX: MOve to game state object... 

def game_thread():
	global DRAW
	global STATE
	global numEnemies
	global numBullets
	global bulletSpawnOk

	def spawn_enemy():
		x, y, xVel, yVel = (0, 0, 0, 0)
		spawnType = random.randint(0, 7)

		"""
		SPAWN LOCATION -- corners and edges
		"""
		if spawnType == 0:
			# TOP RIGHT
			x = MIN_X
			y = MAX_Y
			xVel = random.randint(ASTEROID_VEL_MAG_MIN, ASTEROID_VEL_MAG_MAX)
			yVel = -random.randint(ASTEROID_VEL_MAG_MIN, ASTEROID_VEL_MAG_MAX)

		elif spawnType == 1:
			# BOTTOM RIGHT
			x = MIN_X
			y = MIN_Y
			xVel = random.randint(ASTEROID_VEL_MAG_MIN, ASTEROID_VEL_MAG_MAX)
			yVel = random.randint(ASTEROID_VEL_MAG_MIN, ASTEROID_VEL_MAG_MAX)

		elif spawnType == 2:
			# BOTTOM LEFT
			x = MAX_X
			y = MIN_Y
			xVel = -random.randint(ASTEROID_VEL_MAG_MIN, ASTEROID_VEL_MAG_MAX)
			yVel = random.randint(ASTEROID_VEL_MAG_MIN, ASTEROID_VEL_MAG_MAX)

		elif spawnType == 3:
			# TOP LEFT
			x = MAX_X
			y = MAX_Y
			xVel = -random.randint(ASTEROID_VEL_MAG_MIN, ASTEROID_VEL_MAG_MAX)
			yVel = -random.randint(ASTEROID_VEL_MAG_MIN, ASTEROID_VEL_MAG_MAX)

		elif spawnType == 4:
			# TOP EDGE
			x = random.randint(MIN_X, MAX_X)
			y = MAX_Y
			xVel = random.randint(ASTEROID_VEL_MAG_MIN, ASTEROID_VEL_MAG_MAX)
			xVel *= 1 if random.randint(0, 1) else -1
			yVel = -random.randint(ASTEROID_VEL_MAG_MIN, ASTEROID_VEL_MAG_MAX)

		elif spawnType == 5:
			# RIGHT EDGE
			x = MIN_X
			y = random.randint(MIN_Y, MAX_Y)
			xVel = random.randint(ASTEROID_VEL_MAG_MIN, ASTEROID_VEL_MAG_MAX)
			yVel = random.randint(ASTEROID_VEL_MAG_MIN, ASTEROID_VEL_MAG_MAX)
			yVel *= 1 if random.randint(0, 1) else -1

		elif spawnType == 6:
			# BOTTOM EDGE
			x = random.randint(MIN_X, MAX_X)
			y = MIN_Y
			xVel = random.randint(ASTEROID_VEL_MAG_MIN, ASTEROID_VEL_MAG_MAX)
			xVel *= 1 if random.randint(0, 1) else -1
			yVel = random.randint(ASTEROID_VEL_MAG_MIN, ASTEROID_VEL_MAG_MAX)

		elif spawnType == 7:
			# LEFT EDGE
			x = MAX_X
			y = random.randint(MIN_Y, MAX_Y)
			xVel = -random.randint(ASTEROID_VEL_MAG_MIN, ASTEROID_VEL_MAG_MAX)
			yVel = random.randint(ASTEROID_VEL_MAG_MIN, ASTEROID_VEL_MAG_MAX)
			yVel *= 1 if random.randint(0, 1) else -1

		radius = random.randint(ASTEROID_MIN_RADIUS, ASTEROID_MAX_RADIUS)

		e = Asteroid(x, y, r=CMAX, g=CMAX, b=0, radius=radius)
		e.xVel = xVel
		e.yVel = yVel
		#e.thetaRate = random.uniform(-math.pi/100, math.pi/100)

		e.thetaRate = random.uniform(ASTEROID_SPIN_VEL_MAG_MIN,
									ASTEROID_SPIN_VEL_MAG_MAX)
		e.thetaRate *= 1 if random.randint(0, 1) else -1

		DRAW.objects.append(e)
		STATE.asteroids.append(e)

	def spawn_particles(x, y):
		np = random.randint(PARTICLE_SPAWN_MIN,
							PARTICLE_SPAWN_MAX)
		for i in range(np):
			p = Particle(x, y, CMAX, CMAX, CMAX)
			p.xVel = random.randint(PARTICLE_MIN_X_VEL,
									PARTICLE_MAX_X_VEL)
			p.yVel = random.randint(PARTICLE_MIN_Y_VEL,
									PARTICLE_MAX_Y_VEL)
			DRAW.objects.append(p)

	# Player Object
	ship = Ship(0, 0, rgb=COLOR_PINK, radius=SHIP_SIZE)
	healthbar = HealthBar(0, 0, r=0, g=CMAX, b=0, radius=BALL_RADIUS/2)

	# Initial placement
	ship.x = (MIN_X + MAX_X) /2
	ship.y = (MAX_Y - MIN_Y) /2
	healthbar.x = ship.x
	healthbar.y = ship.y - 2500

	DRAW.objects.append(ship)
	DRAW.objects.append(healthbar)

	STATE.ship = ship
	STATE.healthbar = healthbar

	thread.start_new_thread(joystick_thread, ())

	while True:
		try:

			"""
			Game Events
			"""
			if numEnemies < MAX_NUM_ENEMIES and random.randint(0, 5) == 0:
				spawn_enemy()

			if not STATE.gameOver and numBullets < MAX_NUM_BULLETS:
				bulletSpawnOk = True
			else:
				bulletSpawnOk = False

			if STATE.gameOver and random.randint(0, 20) == 0:
				x = random.randint(MIN_X, MAX_X)
				y = random.randint(MIN_Y, MAX_Y)
				spawn_particles(x, y)

			"""
			Collision Detection
			"""
			# Populate lists
			# TODO: Let's not have to continually rebuild these
			ship = None
			healthbar = None
			bullets = []
			enemies = []
			particles = []

			for obj in DRAW.objects:
				if type(obj) == Asteroid:
					enemies.append(obj)
				elif type(obj) == Particle:
					particles.append(obj)
				elif type(obj) == Bullet:
					bullets.append(obj)
				elif type(obj) == Ship:
					ship = obj
				elif type(obj) == HealthBar:
					healthbar = obj

			# Bullet-enemy collisions
			for b in bullets:
				for e in enemies:
					if e.checkCollide(b) and not e.destroy:
						b.destroy = True
						e.subtract(ASTEROID_HEALTH_BULLET_HIT)
						if e.health <= 0:
							e.destroy = True
							ch = exp.play()
							spawn_particles(e.x, e.y)
						else:
							e.flash = 4	#TCo :  Flash effect lasts two frames

			# Player-enemy collisions
			# XXX/FIXME -- nesting hell! ahhh! cleanup, cleanup!
			if not ship:
				pass

			else:
				for e in enemies:
					if e.destroy:
						continue
					if e.checkCollide(ship):
						e.destroy = True
						ch = exp.play()
						spawn_particles(e.x, e.y)

						if not SHIP_IS_INVINCIBLE:
							STATE.healthbar.subtract(SHIP_HEALTH_ASTEROID_HIT)

							# GAME OVER!
							if STATE.healthbar.health <= 0:
								ship.destroy = True
								healthbar.destroy = True
								spawn_particles(ship.x, ship.y)
								STATE.gameOver = True
								print "Game Over!"

			numEnemies = 0
			numBullets = 0

			"""
			Handle Onscreen Objects
			"""
			for i in range(len(DRAW.objects)):

				# XXX/FIXME/ANNOYING -- multithreaded, 
				# sometimes 'i' disappears from list
				# XXX -- find out where this happens and fix
				if i >= len(DRAW.objects):
					print "Weird out of range error at i=%d" %i
					break

				obj = DRAW.objects[i]

				# PLAYER
				if type(obj) == Ship:
					continue

				# BULLETS
				elif type(obj) == Bullet:
					# XXX Recounted each iter due to terrible design 
					numBullets += 1
					x = obj.x
					y = obj.y
					x += BULLET_SPEED * math.cos(obj.theta)
					y += BULLET_SPEED * math.sin(obj.theta)
					if x < MIN_X or x > MAX_X or y < MIN_Y or y > MAX_Y :
						obj.destroy = True
						continue
					obj.x = x
					obj.y = y

				elif type(obj) == Asteroid:
					# XXX Recounted each iter due to terrible design 
					numEnemies += 1
					x = obj.x
					y = obj.y
					x += obj.xVel
					y += obj.yVel
					if x < MIN_X or x > MAX_X or y < MIN_Y or y > MAX_Y :
						obj.destroy = True
						continue
					obj.x = x
					obj.y = y
					obj.theta += obj.thetaRate
					#TCo : decrease number of flash frames
					if obj.flash:
						obj.flash -= 1 

				elif type(obj) == Particle:
					x = obj.x
					y = obj.y
					x += obj.xVel
					y += obj.yVel

					if x < MIN_X or x > MAX_X or y < MIN_Y or y > MAX_Y :
						obj.destroy = True
						continue
					obj.x = x
					obj.y = y

					obj.life -= 1
					if obj.life <= 0:
						obj.destroy = True
						continue

			time.sleep(0.02)

		except Exception as e:
			import sys, traceback
			print '\n---------------------'
			print 'GAME Exception: %s' % e
			traceback.print_tb(sys.exc_info()[2])
			print "---------------------\n"
			time.sleep(0.02)

def main(argv):
	load_sim = 0
	try:
		opts, args = getopt.getopt(argv, "hs",["help", "simulator"])
	except getopt.GetoptError:
		print "python main.py [-sh]"
		sys.exit(2)
	for opt, args in opts:
		if opt in ('-h', '--help'):
			print "python main.py [-sh]"
			print "Options:"
			print " --help - this message"
			print " --simulator - enable on-screen simulator, disable laser output"
			sys.exit(2)
		elif opt in ('-s', '--simulator'):
			load_sim = 1

	thread.start_new_thread(dac_thread, (load_sim,))
	thread.start_new_thread(game_thread, ())

	while True:
		# 2000000 causes OverflowError on Windows 8.1, Python 2.7 system
		time.sleep(2000000)


if __name__ == "__main__":
	main(sys.argv[1:])
