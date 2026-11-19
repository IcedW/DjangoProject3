from django.db import models
from django.db.models import Q, F
from django.db.models.functions import Lower
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


class Category(models.Model):
    """Категорії товарів"""
    name = models.CharField(max_length=100, unique=True, verbose_name="Назва категорії")
    slug = models.SlugField(max_length=120, unique=True,
                            help_text="URL-friendly назва")  # https://netpeak.net/uk/blog/shcho-take-url-slug-i-yak-zrobiti-yogo-seo-druzhnim/
    description = models.TextField(blank=True, verbose_name="Опис")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")

    class Meta:  # мета-інформація про модель, яка не є полями бази даних, але впливає на поведінку моделі, наприклад, на те, як вона відображається в адміністративній панелі або як сортуються записи
        verbose_name = "Категорія"
        verbose_name_plural = "Категорії"
        ordering = ['name']
        indexes = [
            models.Index(fields=['created_at'], name='category_created_idx'),
        ]
        constraints = [
            # назва і slug не можуть бути порожніми рядками
            models.CheckConstraint(
                condition=Q(name__regex=r'\S'),
                name='category_name_not_blank',
            ),
            models.CheckConstraint(
                condition=Q(slug__regex=r'\S'),
                name='category_slug_not_blank',
            ),
            # унікальність назви без урахування регістру ("Ноутбуки" == "ноутбуки")
            models.UniqueConstraint(
                Lower('name'),
                name='category_name_ci_unique',
            ),
        ]

    def __str__(self):
        return self.name


class Manufacturer(models.Model):
    """Виробники (компанії)"""
    name = models.CharField(max_length=150, unique=True, verbose_name="Назва виробника")
    country = models.CharField(max_length=100, verbose_name="Країна")
    website = models.URLField(max_length=200, blank=True, null=True, verbose_name="Веб-сайт")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    logo = models.ImageField(upload_to='manufacturers/logos/', blank=True, null=True, verbose_name="Логотип")
    established_year = models.PositiveIntegerField(
        validators=[MinValueValidator(1800), MaxValueValidator(2026)],
        blank=True, null=True,
        verbose_name="Рік заснування"
    )

    class Meta:
        verbose_name = "Виробник"
        verbose_name_plural = "Виробники"
        ordering = ['name']
        indexes = [
            models.Index(fields=['country'], name='manufacturer_country_idx'),
            models.Index(fields=['country', 'name'], name='manufacturer_country_name_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(name__regex=r'\S'),
                name='manufacturer_name_not_blank',
            ),
            # рік заснування в допустимому діапазоні (перевірка на рівні БД, а не лише валідатора)
            models.CheckConstraint(
                condition=(
                        Q(established_year__isnull=True)
                        | Q(established_year__gte=1800, established_year__lte=2026)
                ),
                name='manufacturer_year_range',
            ),
            models.UniqueConstraint(
                Lower('name'),
                name='manufacturer_name_ci_unique',
            ),
        ]

    def __str__(self):
        return self.name


class Product(models.Model):
    """Товари / Продукти"""
    STATUS_CHOICES = [
        ('draft', 'Чернетка'),
        ('published', 'Опубліковано'),
        ('archived', 'Архівовано'),
    ]

    # основна інформація
    name = models.CharField(max_length=200, verbose_name="Назва товару")
    slug = models.SlugField(max_length=250, unique=True, verbose_name="Slug")
    description = models.TextField(verbose_name="Опис")
    short_description = models.CharField(max_length=300, blank=True, verbose_name="Короткий опис")

    # зв'язки (ForeignKey + ManyToMany)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,  # не дозволяємо видаляти категорію, якщо є товари
        related_name='products',  # дозволяє отримувати всі товари категорії через category.products
        verbose_name="Категорія"
    )

    manufacturer = models.ForeignKey(
        Manufacturer,
        on_delete=models.SET_NULL,  # якщо виробник видаляється, то поле стає null, але товар не видаляється
        null=True,
        blank=True,  # дозволяє залишити поле порожнім при створенні/редагуванні товару
        related_name='products',
        verbose_name="Виробник"
    )

    # ціни та кількість
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Ціна"
    )
    discount_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Ціна зі знижкою"
    )
    stock_quantity = models.PositiveIntegerField(default=0, verbose_name="Кількість на складі")

    # додаткові поля різних типів
    sku = models.CharField(max_length=50, unique=True, verbose_name="Артикул (SKU)")
    weight = models.FloatField(null=True, blank=True, verbose_name="Вага (кг)")
    is_available = models.BooleanField(default=True, verbose_name="Доступний для продажу")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name="Статус"
    )
    tags = models.JSONField(default=list, blank=True, verbose_name="Теги")  # сучасний спосіб зберігання списку

    # дата і час
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата створення")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата оновлення")
    published_at = models.DateField(null=True, blank=True, verbose_name="Дата публікації")

    # ManyToMany приклад (якщо потрібні додаткові категорії)
    additional_categories = models.ManyToManyField(
        Category,
        related_name='additional_products',
        blank=True,
        verbose_name="Додаткові категорії"
    )

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товари"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['price']),
            models.Index(fields=['status']),
            # типовий запит каталогу: товари категорії з певним статусом
            models.Index(fields=['category', 'status'], name='product_category_status_idx'),
            models.Index(fields=['manufacturer', 'status'], name='product_manuf_status_idx'),
            # сортування за датою публікації
            models.Index(fields=['-published_at'], name='product_published_at_idx'),
            # пошук за назвою
            models.Index(fields=['name'], name='product_name_idx'),
            # частковий індекс: тільки опубліковані й доступні товари (те, що бачить покупець)
            models.Index(
                fields=['category', 'price'],
                name='product_public_cat_price_idx',
                condition=Q(status='published', is_available=True),
            ),
        ]
        constraints = [
            # ціни
            models.CheckConstraint(
                condition=Q(price__gte=0),
                name='product_price_gte_0',
            ),
            models.CheckConstraint(
                condition=Q(discount_price__isnull=True) | Q(discount_price__gte=0),
                name='product_discount_price_gte_0',
            ),
            # ціна зі знижкою має бути меншою за звичайну
            models.CheckConstraint(
                condition=Q(discount_price__isnull=True) | Q(discount_price__lt=F('price')),
                name='product_discount_lt_price',
            ),
            # вага, якщо вказана, має бути додатною
            models.CheckConstraint(
                condition=Q(weight__isnull=True) | Q(weight__gt=0),
                name='product_weight_gt_0',
            ),
            # статус тільки з дозволеного списку
            models.CheckConstraint(
                condition=Q(status__in=['draft', 'published', 'archived']),
                name='product_status_valid',
            ),
            # опублікований товар обов'язково має дату публікації
            models.CheckConstraint(
                condition=~Q(status='published') | Q(published_at__isnull=False),
                name='product_published_has_date',
            ),
            # товар, якого немає на складі, не може бути доступним для продажу
            models.CheckConstraint(
                condition=Q(is_available=False) | Q(stock_quantity__gt=0),
                name='product_available_needs_stock',
            ),
            # назва і артикул не порожні
            models.CheckConstraint(
                condition=Q(name__regex=r'\S') & Q(sku__regex=r'\S'),
                name='product_name_sku_not_blank',
            ),
            # у одного виробника не може бути двох товарів з однаковою назвою
            models.UniqueConstraint(
                fields=['manufacturer', 'name'],
                name='product_manufacturer_name_unique',
            ),
        ]

    def __str__(self):
        return self.name

    def get_final_price(self):
        """Повертає фінальну ціну з урахуванням знижки"""
        return self.discount_price if self.discount_price else self.price