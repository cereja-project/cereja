"""Explicit public exports. This registry must never import feature modules.

The initial surface was characterized at 49701293417af31827027064f5943c0a163b5b6d.
Keep accidental-but-existing aliases until a separately reviewed API change.
"""

import sys as _sys


def _objects(module, names):
    return {name: (module, name) for name in names.split()}


def _modules(package, names):
    return {name: (f"{package}.{name}", None) for name in names.split()}


_CONTEXT = {
    **_objects("cereja.system._context.models", """
        ContextCacheClearReport ContextCacheInfo ContextCacheWarning
        ContextResponse ContextResult ContextSnippet SkippedFile
    """),
    **_objects("cereja.system._context.cache_db", "CacheDatabaseUnavailable"),
    **_objects("cereja.system._context.cache", "clear_context_cache get_context_cache_info"),
    **_objects("cereja.system._context.query", "context_response_to_dict"),
    **_objects("cereja.system._context.search", "list_text_context search_text_context"),
}

EXPORTS = {
    "cereja.utils": {
        **_objects("cereja.utils._utils", """
            CjTest DataAnalyzer DataIterator PoolMeta SingletonMeta Source SourceCodeAnalyzer
            camel_case_to_snake camel_to_snake can_do check_type_on_sequence chunk clipboard
            combinations combinations_sizes combine_with_all decode_coordinates dict_append
            dict_filter_value dict_max_value dict_min_value dict_to_tuple dict_values_len
            encode_coordinates fill get_attr_if_exists get_batch_strides get_implements
            get_instances_of get_zero_mask group_by has_length import_string install_if_not
            invert_dict is_indexable is_iterable is_numeric_sequence is_sequence list_methods
            list_to_tuple logger_level map_values module_references obj_repr prune_values
            rescale_values sample set_log_level snake_case_to_camel sort_dict split_sequence
            str_gen string_to_literal to_tuple truncate type_table_of value_from_memory
            visualize_sample
        """),
        **_objects("cereja.utils.version", "get_version get_version_pep440_compliant latest_git"),
        **_objects("cereja.utils.time", "Timer set_interval time_format"),
        **_objects("cereja.utils.git.repository", "GitRepository"),
        **_modules("cereja.utils", "colab colors decorators git time typography version"),
        "stride_values": ("cereja.utils._utils", "get_batch_strides"),
    },
    "cereja.system": {
        **_objects("cereja.system._path", """
            Path TempDir change_date_from_path clean_dir file_name get_base_dir
            group_path_from_dir mkdir normalize_path
        """),
        **_objects("cereja.system.commons", "memory_of_this memory_usage run_on_terminal thread_monitor"),
        **_objects("cereja.system._repository_files", "RepositoryFile iter_repository_files"),
        **_objects("cereja.system._repository_tree", "render_repository_tree"),
        **_CONTEXT,
        **_modules("cereja.system", "commons unicode"),
    },
    "cereja.concurrently": {
        **_objects("cereja.concurrently._concurrence", "TaskList"),
        **_objects("cereja.concurrently.process", "MultiProcess Processor"),
        **_modules("cereja.concurrently", "process"),
        "async_to_sync": ("cereja.concurrently._concurrence", "AsyncToSync"),
        "sync_to_async": ("cereja.concurrently._concurrence", "SyncToAsync"),
    },
    "cereja.array": _objects("cereja.array._array", """
        Matrix apply_proportional_mask array_gen array_randn determinant div dot dotproduct
        flatten get_cols get_min_max get_shape is_empty prod rand_n rand_uniform
        remove_duplicate_items reshape shape_is_ok sub
    """),
    "cereja.file": _objects("cereja.file._io", "FileIO"),
    "cereja.display": _objects("cereja.display._display", "Progress State console"),
    "cereja.date": _objects("cereja.date._datetime", "AmbiguousDateFormatError DateTime"),
    "cereja.hashtools": {
        **_objects("cereja.hashtools._hash", "base64_decode base64_encode is_base64 md5 random_hash"),
        **_objects("cereja.hashtools._crypto", "CryptoError decrypt decrypt_file encrypt encrypt_file generate_key"),
        **_objects("cereja.hashtools._compress", """
            CompressionError CompressionStats CompressionStrategy analyze_data compress
            compress_dir compress_file decompress decompress_dir decompress_file
            get_compression_ratio is_encrypted_archive suggest_strategy
        """),
    },
    "cereja.mathtools": _objects("cereja.mathtools._op", """
        degrees_to_radian distance_between_points estimate greatest_common_multiple imc
        least_common_multiple nth_fibonacci_number percent proportional radian_to_degrees
        theta_angle theta_from_array
    """),
    "cereja.mltools": {
        **_objects("cereja.mltools.split_data", "Corpus"),
        **_objects("cereja.mltools.data", "ConnectValues DataGenerator Freq TfIdf Tokenizer"),
        **_objects("cereja.mltools.pln", "LanguageData LanguageDetector Preprocessor"),
        **_modules("cereja.mltools", "data pln preprocess split_data"),
    },
    "cereja._requests": _modules("cereja._requests", "request"),
    "cereja.config": {
        **_objects("cereja.config.conf", "BasicConfig BASE_DIR PYTHON_VERSION"),
        **_objects("cereja.config._constants", """
            DATA_UNIT_MAP ENG_CONTRACTIONS LANGUAGES NUMBER_WORDS PROXIES_URL
            PUNCTUATION STOP_WORDS VALID_LANGUAGE_CHAR
        """),
        **_modules("cereja.config", "cj_types conf"),
    },
    "cereja.experimental": {
        **_objects("cereja.experimental.commons", "CJDict CJMeta CJOrderedDict ParallelProcess"),
        **_modules("cereja.experimental", "commons"),
    },
    "cereja.geolinear": {
        **_objects("cereja.geolinear.point", "Point"),
        **_objects("cereja.geolinear.utils", "Rotation find_best_locations"),
        **_modules("cereja.geolinear", "point utils"),
    },
    "cereja.scraping": _modules("cereja.scraping", "b3"),
    "cereja.system._context": {
        **_CONTEXT,
        **_modules("cereja.system._context", "cache cache_db models query search"),
    },
    "cereja.utils.colors": {
        **_objects("cereja.utils.colors._color", "Color"),
        **_objects("cereja.utils.colors.converters", """
            cmyk_to_rgb hex_to_rgb hsl_to_rgb hsv_to_rgb normalize_rgb
            rgb_to_cmyk rgb_to_hex rgb_to_hsl rgb_to_hsv
        """),
        **_modules("cereja.utils.colors", "converters"),
    },
    "cereja.utils.typography": {
        **_objects("cereja.utils.typography._typography", "Typography"),
        **_objects("cereja.utils.typography.converters", """
            em_to_pt em_to_px pt_to_em pt_to_px pt_to_rem px_to_pt rem_to_pt rem_to_px
        """),
        **_modules("cereja.utils.typography", "converters"),
    },
    "cereja.utils.git": _modules("cereja.utils.git", "exceptions repository runner"),
    "cereja.wcag": {
        **_objects("cereja.wcag.validator._color", "contrast_checker"),
        **_modules("cereja.wcag", "validator"),
    },
    "cereja.wcag.validator": _objects("cereja.wcag.validator._color", "contrast_checker"),
}

# The root retains the historical re-exports, but this only combines strings.
_ROOT_PACKAGES = "utils display file array system concurrently mltools date hashtools mathtools"
EXPORTS["cereja"] = {
    name: target
    for package in _ROOT_PACKAGES.split()
    for name, target in EXPORTS[f"cereja.{package}"].items()
}
EXPORTS["cereja"].update({
    **_modules("cereja", """
        array concurrently config date display experimental file geolinear hashtools
        mathtools mltools scraping system utils wcag
    """),
    "conf": ("cereja.config.conf", None),
    "request": ("cereja._requests.request", None),
    "Unicode": ("cereja.system.unicode", "Unicode"),
    "VERSION": ("cereja._version", "VERSION"),
    "NON_BMP_SUPPORTED": ("cereja._terminal", "NON_BMP_SUPPORTED"),
    "print_cereja_version": ("cereja", "print_cereja_version"),
})

# Never import Win32 to determine availability: it changes process DPI settings.
WINDOWS_EXPORTS = {
    package: _objects("cereja.system._win32", "Window Keyboard Mouse play_alert_sound")
    for package in ("cereja", "cereja.system")
}
if _sys.platform == "win32":
    for _package, _exports in WINDOWS_EXPORTS.items():
        EXPORTS[_package].update(_exports)

# This package already restricted star imports before the migration.
STAR_EXPORTS = {
    "cereja.system._context": (
        "ContextCacheInfo", "ContextCacheClearReport", "ContextCacheWarning",
        "CacheDatabaseUnavailable", "ContextSnippet", "ContextResult", "SkippedFile",
        "ContextResponse", "search_text_context", "list_text_context",
        "context_response_to_dict", "get_context_cache_info", "clear_context_cache",
    ),
}
