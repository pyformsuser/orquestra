from django.core.management.base import BaseCommand, CommandError
from django.apps import apps

import inspect, os, shutil, pkgutil, importlib
from django.conf import settings
from django.conf.urls import url
from django.template.loader import render_to_string
from orquestra.plugins.baseplugin import LayoutPositions, BasePlugin
from pyforms_web.web.BaseWidget import BaseWidget


class PluginsManager(object):

	def __init__(self):
		self._plugins_list = []
		self.search_4_plugins()

	def append(self, plugin): self._plugins_list.append(plugin)

	@property
	def plugins(self): return self._plugins_list

	
	def menu(self, user=None, menus=[]):
		res = []
		for plugin_class in self.plugins:
			if not hasattr(plugin_class, 'menu') or not plugin_class.menu in menus: continue

			add = False
			if hasattr(plugin_class, 'groups'):
				if 'superuser' in plugin_class.groups and user.is_superuser:  add = True
				if user.groups.filter(name__in=plugin_class.groups).exists():  add = True
			else:
				add = True

			if add: res.append(plugin_class)

		return res



	def export_urls_file(self, filename):
		out = open(filename, 'w')

		out.write( "from django.conf.urls import url\nfrom django.views.decorators.csrf import csrf_exempt\n" )
		for plugin_class in self.plugins:
			if issubclass(plugin_class, BaseWidget): continue

			out.write( 
				"from {0} import {1}\n".format(
					plugin_class.__module__,
					plugin_class.__name__
				) 
			)
		out.write( "\n" )

		out.write( "urlpatterns = [\n" )
		for plugin_class in self.plugins:
			if issubclass(plugin_class, BaseWidget): continue
			plugin = plugin_class()

			for view in plugin.views:
				if not hasattr(plugin, '%s_argstype' % view.__name__): continue
				if hasattr(plugin, '%s_name' % view.__name__):
					out.write( "\turl(r'^{0}', {1}, name='{2}'),\n".format( 
						BasePlugin.viewURL(plugin_class, view), 
						BasePlugin.viewName(plugin_class, view),
						getattr(plugin, '%s_name' % view.__name__)
					))
				else:
					out.write( "\turl(r'^%s', %s),\n" % ( 
						BasePlugin.viewURL(plugin_class, view), 
						BasePlugin.viewName(plugin_class, view) ) )
		out.write( "]" )

		out.close()



	def export_js_file(self, filename):
		out = open(filename, 'w')
		
		for plugin_class in self.plugins:
			if issubclass(plugin_class, BaseWidget):

				out.write( "function run%s(){\n" % ( plugin_class.__name__.capitalize(), ) )
				out.write( "\tloading();\n" )
				out.write( "\tactivateMenu('menu-{0}');\n".format( 	 plugin_class.__name__.lower() ) )
				out.write( "\trun_application('{0}.{1}');\n".format( plugin_class.__module__,plugin_class.__name__ ) )
				out.write( "}\n" )
				out.write( "\n" )
				
			else:
				plugin = plugin_class()
				for view in plugin.views:
					if not hasattr(plugin, '%s_position' % view.__name__): continue
					if not hasattr(plugin, '%s_argstype' % view.__name__): continue

					prefix = plugin_class.__name__.capitalize()
					sufix = view.__name__.capitalize()
					if prefix==sufix: sufix=''
					params = [x for x in inspect.getargspec(view)[0][1:]]

					out.write( "function run%s%s(%s){\n" % ( prefix, sufix, ','.join(params) ) )
					out.write( "\tloading();\n" )
					out.write( "\tactivateMenu('menu-%s');\n" % plugin.anchor )

					position = getattr(plugin, '%s_position' % view.__name__)
					
					label_attr = '{0}_label'.format(view.__name__)
					label = getattr(plugin, label_attr) if hasattr(plugin, label_attr) else view.__name__
					
					breadcrumbs = BasePlugin.viewBreadcrumbs(plugin, view)
					#if position==LayoutPositions.TOP:
					#	out.write( "\tshowBreadcrumbs(%s, '%s');\n" % (breadcrumbs, label) )
					
					
					if hasattr(plugin, '%s_js' % view.__name__):
						javascript = getattr(plugin, '%s_js' % view.__name__)
						out.write( """\t%s\n""" % javascript )
					else:		
						if position==LayoutPositions.HOME:
							out.write( "\tclearInterval(refreshEvent);\n")
							out.write( """
							select_main_tab();
							$('#top-pane').load("/plugins/%s", function(response, status, xhr){
								if(status=='error') error_msg(xhr.status+" "+xhr.statusText+": "+xhr.responseText);
								not_loading();
							});\n""" % BasePlugin.viewJsURL(plugin_class, view) )
						
						if position==LayoutPositions.NEW_TAB:

							out.write('add_tab("{0}", "{1}", "/plugins/{2}");'.format(view.__name__, label, BasePlugin.viewJsURL(plugin_class, view)) )

						if position==LayoutPositions.WINDOW:
							out.write( "\tloading();" )
							out.write( "\t$('#opencsp-window').dialog('open');\n" )
							out.write( """\t$('#opencsp-window').load("/plugins/%s",function() {\n"""  %  BasePlugin.viewJsURL(plugin_class, view) )
							out.write( """\t\tnot_loading();$(this).scrollTop($(this)[0].scrollHeight);\n""" )
							out.write( """\t});\n""" )
						if position==LayoutPositions.NEW_WINDOW:
							out.write( """window.open('/plugins/%s');""" % BasePlugin.viewJsURL(plugin_class, view) )

					out.write( "}\n" )
					out.write( "\n" )
			
		views_ifs = []
		home_function = 'function(){};';
		for plugin_class in self.plugins:
			if issubclass(plugin_class, BaseWidget):
				function = plugin_class.__name__.capitalize()
				anchor 	 = plugin_class.__name__.lower()
				views_ifs.append( "\tif(view=='{0}') run{1}.apply(null, params);\n".format(anchor, function) )
			else:
			
				plugin = plugin_class()

				for index, view in enumerate(plugin.views):
					if not hasattr(plugin, '%s_position' % view.__name__): continue
					if not hasattr(plugin, '%s_argstype' % view.__name__): continue

					prefix = plugin_class.__name__.capitalize()
					sufix = view.__name__.capitalize()
					if prefix==sufix: sufix=''
					params = [x for x in inspect.getargspec(view)[0][1:]]
					if index==0:
						home_function = "run%s%s.apply(null, params);" % ( prefix, sufix)


					views_ifs.append( "\tif(view=='%s') run%s%s.apply(null, params);\n" % ( BasePlugin.viewJsAnchor(plugin_class, view), prefix, sufix) )


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





OUTPUT_PLUGINS_DIR = os.path.join( settings.BASE_DIR, 'orquestra_plugins')


class Command(BaseCommand):
	help = 'Setup orquestra plugins'

	def handle(self, *args, **options):
		manager = PluginsManager()


		if not os.path.exists(OUTPUT_PLUGINS_DIR): os.makedirs(OUTPUT_PLUGINS_DIR)
		manager.export_urls_file( os.path.join(OUTPUT_PLUGINS_DIR,'urls.py') )
		
		static_dir = os.path.join(OUTPUT_PLUGINS_DIR, 'static')
		if not os.path.exists(static_dir): os.makedirs(static_dir)

		js_dir = static_dir
		if not os.path.exists(js_dir): os.makedirs(js_dir)
		

		print("Updating plugins scripts")
		manager.export_js_file( os.path.join(js_dir,'commands.js') )
		
		#environment_file = os.path.join(OUTPUT_PLUGINS_DIR,'environments.py')
		#self.export_environments(environment_file)