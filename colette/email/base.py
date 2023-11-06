from abc import ABC, abstractmethod
from colette.models import Solution

from jinja2 import Template


class Email(ABC):
    def __init__(self, solution: Solution):
        self.solution = solution
        self.templates = {}

    def add_template(self, template: Template):
        self.templates.append(template)

    @abstractmethod
    def send_email(self):
        pass
