import re
from typing import Optional

from credsweeper.app import APP_PATH
from credsweeper.config.config import Config
from credsweeper.credentials.line_data import LineData
from credsweeper.utils.util import Util
from tests.filters.conftest import LINE_VALUE_PATTERN


def config() -> Config:
    config_dict = Util.json_load(APP_PATH / "secret" / "config.json")

    config_dict["use_filters"] = True
    config_dict["find_by_ext"] = False
    config_dict["depth"] = 0
    config_dict["doc"] = False
    config_dict["size_limit"] = None
    return Config(config_dict)


def get_line_data(test_config: Config = config(),
                  file_path: str = "",
                  line: str = "",
                  pattern: Optional[re.Pattern] = None) -> LineData:
    pattern = re.compile(pattern) if pattern else re.compile(LINE_VALUE_PATTERN)
    line_data = LineData(test_config, line, 0, 1, file_path, Util.get_extension(file_path), "info", pattern)
    assert line_data.value  # most important member for filters
    return line_data
