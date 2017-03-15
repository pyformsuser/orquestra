from django.core.management.base import BaseCommand, CommandError
from django.apps import apps

import inspect, os, shutil, pkgutil, importlib
from django.conf import settings
from pysettings import conf
from django.conf.urls import url
from django.template.loader import render_to_string
from orquestra.plugins import LayoutPositions
from pyforms_web.web.BaseWidget import BaseWidget


class PluginsManager(object):

	def __init__(self):
		self._plugins_list = []
		self.search_4_plugins()

	def append(self, plugin): self._plugins_list.append(plugin)

	@property
	def plugins(self): return self._plugins_list

	
	def menu(self, user=None, menus=None):
		res = []
		for plugin_class in self.plugins:
			if 	menus and \
				(
					not hasattr(plugin_class, 'menu') or \
					not plugin_class.menu in menus
				): continue

			add = False
			if hasattr(plugin_class, 'groups'):
				if 'superuser' in plugin_class.groups and user.is_superuser:  add = True
				if user.groups.filter(name__in=plugin_class.groups).exists():  add = True
			else:
				add = True

			if add: res.append(plugin_class)

		return res



	



	def export_js_file(self, filename):
		out = open(filename, 'w')
		
		for plugin_class in self.plugins:
			if issubclass(plugin_class, BaseWidget):
				print plugin_class
				out.write( "function run%s(){\n" % ( plugin_class.__name__.capitalize(), ) )
				out.write( "\tloading();\n" )
				out.write( "\tactivateMenu('menu-{0}');\n".format( 	 plugin_class.__name__.lower() ) )
				out.write( "\trun_application('{0}.{1}');\n".format( plugin_class.__module__,plugin_class.__name__ ) )
				out.write( "}\n" )
				out.write( "\n" )
			
		views_ifs = []
		
		for plugin_class in self.plugins:
			if issubclass(plugin_class, BaseWidget):
				function = plugin_class.__name__.capitalize()
				anchor 	 = plugin_class.__name__.lower()
				function_call = "run{0}.apply(null, params);".format(function)
				views_ifs.append( "\tif(view=='{0}') {1}\n".format(anchor, function_call) )
		
		home_function = conf.ORQUESTRA_HOME_FUNCTION

		out.write( render_to_string( os.path.join( os.path.dirname(__file__), '..', '..','templates','plugins','commands.js'), {'views_ifs': views_ifs, 'home_function':home_function} ) )
		out.close()


	def search_4_plugins(self):
		
		for app in apps.get_app_configs():
			if hasattr(app, 'orquestra_plugins'):
				for modulename in app.orquestra_plugins:
					print("Found plugin: {0}".format(modulename))					
					modules = modulename.split('.')
					moduleclass = __import__( '.'.join(modules[:-1]) , fromlist=[modules[-1]] )
					self.append( getattr(moduleclass, modules[-1]) )



class Command(BaseCommand):
	help = 'Setup orquestra plugins'

	def handle(self, *args, **options):
		manager = PluginsManager()

		static_dir = os.path.join( settings.BASE_DIR, 'static', 'js')
		if not os.path.exists(static_dir): os.makedirs(static_dir)
		
		print("updating plugins scripts")
		manager.export_js_file( os.path.join(static_dir,'commands.js') )
		