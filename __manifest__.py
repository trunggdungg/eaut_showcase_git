{
    'name': 'EAUT Showcase Website',
    'version': '1.0',
    'summary': 'Website giới thiệu dự án, sản phẩm và năng lực công nghệ của EAUT',
    'description': """
    EAUT Showcase là module website dùng để giới thiệu các dự án,
    sản phẩm, giải pháp công nghệ và thành tựu nổi bật của EAUT.

    Module cung cấp các trang danh sách dự án, chi tiết dự án,
    thông tin tác giả, hình ảnh, video và các nội dung giới thiệu
    được xây dựng bằng Odoo QWeb.
""",
    'category': 'Website',
    'author': 'Trugn Dugn',
    'depends': ['website', 'mail', 'portal'],
    'data': [
        'security/ir.model.access.csv',
        'data/eaut_showcase_data.xml',
        'data/eaut_showcase_advisor_demo_data.xml',
        'data/eaut_showcase_cron_data.xml',
        'views/eaut_showcase_category_views.xml',
        'views/eaut_showcase_status_views.xml',
        'views/eaut_showcase_creator_views.xml',
        'views/eaut_showcase_interest_views.xml',
        'views/eaut_showcase_comment_views.xml',
        'views/eaut_showcase_term_views.xml',
        'views/eaut_showcase_advisor_registration_views.xml',
        'views/eaut_showcase_advisor_registration_kanban_views.xml',
        'views/eaut_showcase_creator_kanban_views.xml',
        'views/eaut_showcase_portal_advisor_views.xml',
        'views/eaut_showcase_portal_home_views.xml',
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
    'icon': 'static/description/icon.png',
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
