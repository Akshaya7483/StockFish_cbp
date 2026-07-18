from math import exp
from time import perf_counter

from accuracy import Accuracy
from accuracy_summary import AccuracySummary
from config import ACCURACY_DECAY


class AccuracyEngineStage:
    """
    Accuracy Engine — Step 5 (game statistics).

    Generates one Accuracy object per Review (per-move CPL + accuracy%),
    aggregates them into player-level statistics, and rolls those up into
    game-level statistics (overall averages + best/worst player). It performs
    no new per-move calculations, no weighted averages, and no timeline or API
    changes. It consumes only ctx.reviews / ctx.accuracy and adds no Stockfish
    searches.
    """

    def run(self, ctx):
        start = perf_counter()

        accuracy = []
        evaluated = 0
        failed = 0
        total_ms = 0.0

        for review in ctx.reviews:
            item_start = perf_counter()
            try:
                obj = self._create_accuracy(review)
                evaluated += 1
            except Exception as e:
                obj = Accuracy(review=review, error=str(e))
                failed += 1
            total_ms += (perf_counter() - item_start) * 1000

            accuracy.append(obj)

        total_moves = len(ctx.reviews)

        ctx.accuracy = accuracy
        ctx.accuracy_statistics = {
            "total_moves": total_moves,
            "evaluated_moves": evaluated,
            "failed_moves": failed,
            "average_generation_time_ms": round(
                total_ms / total_moves,
                4
            ) if total_moves else 0.0,
        }

        # Merge in per-player aggregates without touching the fields above.
        player_statistics = self._compute_player_statistics(accuracy)
        ctx.accuracy_statistics.update(player_statistics)

        # Roll player aggregates up into game-level statistics.
        ctx.accuracy_statistics.update(
            self._compute_game_statistics(accuracy, player_statistics)
        )

        # Map the computed statistics into a typed summary object. No new
        # calculations — pure value mapping.
        ctx.accuracy_summary = self._build_accuracy_summary(ctx.accuracy_statistics)

        ctx.accuracy_generation_time_ms = round(
            (perf_counter() - start) * 1000,
            4
        )

        return ctx

    # ------------------------------------
    # Helpers
    # ------------------------------------

    def _create_accuracy(self, review):
        """
        Build an Accuracy object from a Review by copying its centipawn_loss
        and deriving accuracy% from it. No CPL recomputation.
        """
        return Accuracy(
            review=review,
            centipawn_loss=review.centipawn_loss,
            accuracy=self._calculate_accuracy(review.centipawn_loss),
            player=review.candidate.side,
            move_number=review.candidate.move_number,
            metadata={},
            error=None,
        )

    def _calculate_accuracy(self, cpl):
        """
        Convert centipawn loss into a 0-100 accuracy score. Handles the
        None case, clamps to [0, 100] and rounds to 2 decimals. The actual
        shape of the curve is delegated to _accuracy_curve so it can be
        swapped (v1 / Chess.com-like / Lichess-like / custom) without
        touching this stage.
        """
        if cpl is None:
            return None

        score = self._accuracy_curve(cpl)
        score = max(0.0, min(100.0, score))
        return round(score, 2)

    def _compute_player_statistics(self, accuracy_list):
        """
        Aggregate per-move Accuracy objects into per-player statistics.

        Consumes only the Accuracy objects (never Reviews). Objects with an
        error are ignored entirely; None accuracy/CPL values are ignored when
        averaging. A player with no valid samples yields None for that average.
        """
        buckets = {
            "white": {"count": 0, "accuracy": [], "cpl": []},
            "black": {"count": 0, "accuracy": [], "cpl": []},
        }

        for item in accuracy_list:
            if item.error is not None:
                continue

            bucket = buckets.get(item.player)
            if bucket is None:
                continue

            bucket["count"] += 1

            if item.accuracy is not None:
                bucket["accuracy"].append(item.accuracy)
            if item.centipawn_loss is not None:
                bucket["cpl"].append(item.centipawn_loss)

        return {
            "white_moves": buckets["white"]["count"],
            "black_moves": buckets["black"]["count"],
            "white_average_accuracy": self._average(buckets["white"]["accuracy"]),
            "black_average_accuracy": self._average(buckets["black"]["accuracy"]),
            "white_average_cpl": self._average(buckets["white"]["cpl"]),
            "black_average_cpl": self._average(buckets["black"]["cpl"]),
        }

    def _compute_game_statistics(self, accuracy_list, player_statistics):
        """
        Roll per-player aggregates up into game-level statistics.

        Overall averages are computed across all valid Accuracy objects
        (errors ignored, None values skipped). Best/worst player is decided by
        the per-player average accuracy already computed in
        player_statistics; a tie (or missing data) yields None for both.
        """
        valid = [item for item in accuracy_list if item.error is None]

        overall_average_accuracy = self._average(
            [item.accuracy for item in valid if item.accuracy is not None]
        )
        overall_average_cpl = self._average(
            [item.centipawn_loss for item in valid if item.centipawn_loss is not None]
        )

        white_acc = player_statistics.get("white_average_accuracy")
        black_acc = player_statistics.get("black_average_accuracy")

        best_player = None
        best_player_accuracy = None
        worst_player = None
        worst_player_accuracy = None

        if white_acc is not None and black_acc is not None and white_acc != black_acc:
            if white_acc > black_acc:
                best_player, best_player_accuracy = "white", white_acc
                worst_player, worst_player_accuracy = "black", black_acc
            else:
                best_player, best_player_accuracy = "black", black_acc
                worst_player, worst_player_accuracy = "white", white_acc

        return {
            "overall_average_accuracy": overall_average_accuracy,
            "overall_average_cpl": overall_average_cpl,
            "best_player": best_player,
            "best_player_accuracy": best_player_accuracy,
            "worst_player": worst_player,
            "worst_player_accuracy": worst_player_accuracy,
        }

    def _build_accuracy_summary(self, statistics):
        """
        Map the already-computed statistics dict into a typed AccuracySummary.
        Pure value mapping — no calculations.
        """
        return AccuracySummary(
            overall_average_accuracy=statistics.get("overall_average_accuracy"),
            overall_average_cpl=statistics.get("overall_average_cpl"),
            white_moves=statistics.get("white_moves", 0),
            black_moves=statistics.get("black_moves", 0),
            white_average_accuracy=statistics.get("white_average_accuracy"),
            black_average_accuracy=statistics.get("black_average_accuracy"),
            white_average_cpl=statistics.get("white_average_cpl"),
            black_average_cpl=statistics.get("black_average_cpl"),
            best_player=statistics.get("best_player"),
            best_player_accuracy=statistics.get("best_player_accuracy"),
            worst_player=statistics.get("worst_player"),
            worst_player_accuracy=statistics.get("worst_player_accuracy"),
            total_moves=statistics.get("total_moves", 0),
            evaluated_moves=statistics.get("evaluated_moves", 0),
            failed_moves=statistics.get("failed_moves", 0),
        )

    def _average(self, values):
        if not values:
            return None
        return round(sum(values) / len(values), 2)

    def _accuracy_curve(self, cpl):
        """
        Default accuracy curve (v1): gentle exponential decay so that small
        inaccuracies stay near 100% and only large mistakes score low —
        score = 100 * exp(-cpl / ACCURACY_DECAY). Replace this single method
        to adopt a different accuracy model. Returns a raw (unclamped) float.
        """
        return 100.0 * exp(-cpl / ACCURACY_DECAY)
