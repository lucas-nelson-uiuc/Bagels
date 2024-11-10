from datetime import datetime, timedelta

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Label, Static

from bagels.components.barchart import Barchart, BarchartData
from bagels.components.percentage_bar import PercentageBar, PercentageBarItem
from bagels.config import CONFIG
from bagels.queries.categories import get_all_categories_records
from bagels.queries.utils import (get_period_average, get_period_figures,
                                  get_start_end_of_period)


class Insights(Static):
    
    BINDINGS = [
        (CONFIG.hotkeys.home.insights.toggle_use_account, "toggle_use_account", "Toggle use account")
    ]
    
    can_focus = True
    
    def __init__(self, parent: Static, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, id="insights-container", classes="module-container")
        super().__setattr__("border_title", "Insights")
        self.page_parent = parent
        self.use_account = False # insights of specific account if True
    
    def on_mount(self) -> None:
        self.rebuild()
    
    #region Builder
    # -------------- Builder ------------- #

    def rebuild(self) -> None:
        items = self.get_percentage_bar_items()
        self.percentage_bar.set_items(items)
        data = self.get_period_barchart_data()
        self.period_barchart.set_data(data)
        self._update_labels()
    
    def _update_labels(self) -> None:
        current_filter_label = self.query_one(".current-filter-label")
        period_net_label = self.query_one(".period-net")
        period_average_label = self.query_one(".period-average")
        average_label = self.query_one(".average-label")
        
        mode_isIncome = self.page_parent.mode["isIncome"]
        label = "Income" if mode_isIncome else "Expense"
        
        if self.use_account:
            current_filter_label.update(f"{self.page_parent.mode['accountId']['defaultValueText']} {label} of {self.page_parent.get_filter_label()}")
        else:
            current_filter_label.update(f"{label} of {self.page_parent.get_filter_label()}")
        average_label.update(f"{label} per day")
        
        if self.use_account:
            params = {
                **self.page_parent.filter,
                "accountId": self.page_parent.mode["accountId"]["defaultValue"],
                "isIncome": mode_isIncome
            }
        else:
            params = {
                **self.page_parent.filter,
                "isIncome": mode_isIncome
            }
        
        period_net = get_period_figures(**params)
        period_average = get_period_average(period_net, **self.page_parent.filter)
        period_net_label.update(str(period_net))
        period_average_label.update(str(period_average))

    def get_percentage_bar_items(self, limit: int = 5) -> list[PercentageBarItem]:
        if self.use_account:
            category_records = get_all_categories_records(
                **self.page_parent.filter,
                isExpense=not self.page_parent.mode["isIncome"],
                account_id=self.page_parent.mode["accountId"]["defaultValue"]
            )
        else:
            category_records = get_all_categories_records(
                **self.page_parent.filter,
                isExpense=not self.page_parent.mode["isIncome"]
            )
        
        # Sort categories by percentage in descending order
        items = []
        if len(category_records) <= limit:
            # If we have 5 or fewer categories, show them all
            for category in category_records:
                items.append(PercentageBarItem(
                    name=category.name,
                    count=category.percentage,
                    color=category.color
                ))
        else:
            # Show top 4 categories and group the rest as "Others"
            for category in category_records[:limit]:
                items.append(PercentageBarItem(
                    name=category.name,
                    count=category.percentage,
                    color=category.color
                ))
                
            # Sum up the percentages of remaining categories
            others_percentage = sum(cat.percentage for cat in category_records[limit:])
            items.append(PercentageBarItem(
                name="Others",
                count=others_percentage,
                color="white"
            ))
        
        return items

    def get_period_barchart_data(self) -> BarchartData:
        offset_type = self.page_parent.filter["offset_type"]
        offset = self.page_parent.filter["offset"]
        if offset_type == "day":
            return BarchartData(
                amounts=[],
                labels=[]
            )
            
        
        # Get data for each sub-period
        amounts = []
        labels = []
        
        match offset_type:
            case "year":
                # Get start of the target year
                start_date = datetime.now().replace(month=1, day=1, year=datetime.now().year + offset)
                for i in range(12):
                    # Calculate month offset relative to today
                    target_date = start_date.replace(month=i+1)
                    month_offset = (target_date.year - datetime.now().year) * 12 + (target_date.month - datetime.now().month)
                    
                    amount = get_period_figures(
                        offset_type="month",
                        offset=month_offset,
                        isIncome=self.page_parent.mode["isIncome"]
                    )
                    amounts.append(abs(amount))
                    labels.append(target_date.strftime("%b"))
            case "month":
                # Get start and end of target month
                start_date, end_date = get_start_end_of_period(offset, "month")
                
                # Get the Monday of the first week that contains any day of the month
                first_monday = start_date - timedelta(days=start_date.weekday())
                
                for i in range(4):
                    target_date = first_monday + timedelta(weeks=i)
                    week_offset = (target_date - datetime.now()).days // 7
                    
                    amount = get_period_figures(
                        offset_type="week",
                        offset=week_offset,
                        isIncome=self.page_parent.mode["isIncome"]
                    )
                    amounts.append(abs(amount))
                    labels.append(f"w{i+1}")
            case "week":
                start_date, end_date = get_start_end_of_period(
                    offset,
                    offset_type
                )
                days_diff = (end_date - start_date).days + 1
                
                for i in range(days_diff):
                    current_date = start_date + timedelta(days=i)
                    day_offset = (current_date - datetime.now()).days
                    
                    amount = get_period_figures(
                        offset_type="day",
                        offset=day_offset,
                        isIncome=self.page_parent.mode["isIncome"]
                    )
                    amounts.append(abs(amount))
                    labels.append(current_date.strftime("%d"))
            
        return BarchartData(
            amounts=amounts,
            labels=labels
        )

    #region Callbacks
    # ------------- callbacks ------------ #
    def action_toggle_use_account(self) -> None:
        self.use_account = not self.use_account
        self.rebuild()
        
    #region View
    # --------------- View --------------- #

    def compose(self) -> ComposeResult:
        with Horizontal(classes="figures-container"):
            with Container(classes="net container"):
                yield Label(classes="current-filter-label title") # dynamic
                yield Label("Loading...", classes="period-net amount") # dynamic
            with Container(classes="average container"):
                yield Label("<> per day", classes="average-label title") # dynamic
                yield Label("Loading...", classes="period-average amount") # dynamic
            
        self.percentage_bar = PercentageBar()
        self.period_barchart = Barchart()
        yield self.percentage_bar
        yield self.period_barchart