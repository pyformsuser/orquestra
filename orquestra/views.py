import os, simplejson
from django.http 									import HttpResponse
from django.shortcuts 								import render_to_response
from django.contrib.auth.decorators 				import login_required
from orquestra.management.commands.install_plugins 	import PluginsManager
from orquestra.plugins 			 					import MenusPositions
from pyforms_web.web.djangoapp 						import ApplicationsLoader

@login_required
def index(request, app_uid=None):

	manager = PluginsManager()
	
	##### find the style and javscripts files #################################################
	style_files, javascript_files = [], []
	for plugin in manager.plugins:
		for staticfile in (plugin.static_files if hasattr(plugin, 'static_files') else []):
			if staticfile.endswith('.css'): style_files.append(staticfile)
			if staticfile.endswith('.js'):  javascript_files.append(staticfile)
	###########################################################################################

	#### load menus ###########################################################################
	plugins4menus = sorted(manager.menu(request.user), key=lambda x: (x.menu,len(x.menu)) )
	menus 		  = {}
	active_menus  = {}

	running_menu = None
	for plugin_class in plugins4menus:
		menus_options = plugin_class.menu.split('>')

		# used to check if a menu should be activated or not
		active_menus[menus_options[0]] = True

		# if an application is not running ignore the submenus
		if app_uid is None and len(menus_options)>1: continue
		
		menu 			= type('MenuOption', (object,), {})
		menu.menu_place	= menus_options[0]
		menu.uid 		= plugin_class._uid if hasattr(plugin_class,'_uid') else ''
		menu.label 		= plugin_class.label if plugin_class.label else plugin_class.__name__.lower()
		menu.order 		= plugin_class.menu_order if hasattr(plugin_class,'menu_order') else None
		menu.icon  		= plugin_class.icon if hasattr(plugin_class, 'icon') else None
		menu.anchor 	= plugin_class.__name__.lower()
		menu.fullname 	= plugin_class.fullname # full name of the class
		menu.parent_menu= None
		menu.active 	= False
		menu.submenus 	= []
		menu.show_submenu = False
		
		# append main menu
		if len(menus_options)==1:
			menus[plugin_class.__name__] = menu
		
		elif len(menus_options)==2:
			menu.parent_menu = menus[menus_options[1]]
			menus[menus_options[1]].submenus.append( menu )
			#menu.parent_menu.active = True

		if app_uid==plugin_class._uid: 
			running_menu = menu			
			menu.active  = True
			if menu.parent_menu: 
				menu.parent_menu.show_submenu = True
			else:
				menu.show_submenu = True

	## sort menus and submenus ######################################################################
	menus = sorted(menus.values(), key=lambda x: x.order)
	for menu in menus: menu.submenus = sorted(menu.submenus, key=lambda x: x.order)
	#################################################################################################

	if running_menu is None: running_menu = menus[0]
	
	context = {'user': request.user}
	context.update({
		'menu_plugins': menus,
		'active_menus': list(set(active_menus)),
		'styles_files': style_files,
		'javascript_files': javascript_files,
		'running_menu': running_menu
	})

	return render_to_response('authenticated_base.html', context )

