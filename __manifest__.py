{
    'name': 'UIKick - Crowdfunding Website',
    'version': '1.0',
    'summary': 'Kickstarter-style discovery & campaign page (converted from React)',
    'description': """
        Website pages replicating a Kickstarter-like project discovery page
        and campaign detail page, originally built in React + Tailwind and
        ported to Odoo QWeb templates.
    """,
    'category': 'Website',
    'author': 'Trugn Dugn',
    'depends': ['website', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/eaut_showcase_data.xml',
        'views/eaut_showcase_category_views.xml',
        'views/eaut_showcase_status_views.xml',
        'views/eaut_showcase_creator_views.xml',
        'views/eaut_showcase_interest_views.xml',
        'views/eaut_showcase_home_views.xml',
        'views/eaut_showcase_creator_detail_views.xml',
        'views/eaut_showcase_detail_views.xml',
        'views/eaut_showcase_backend_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'eaut_showcase/static/src/css/style.css',
            'eaut_showcase/static/src/js/home.js',
            'eaut_showcase/static/src/js/detail.js',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
