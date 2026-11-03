from .runner import sha256

class VisionModelManager:
    def __init__(self, config): self.config = config
    def status(self):
        checkpoint = self.config.model_root / 'balltrack_best.pth'
        return {'BallTrack': {'installed': checkpoint.is_file(), 'checkpoint': str(checkpoint),
                              'sha256': sha256(checkpoint) if checkpoint.is_file() else None,
                              'validation': 'SEE_RECORDED_BENCHMARK'},
                'RacketPose': {'installed': False, 'validation': 'NOT_IMPLEMENTED'},
                'TrajPred': {'installed': False, 'validation': 'NOT_IMPLEMENTED'}}
