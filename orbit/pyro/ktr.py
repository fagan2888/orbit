import numpy as np
import torch

import pyro
import pyro.distributions as dist

torch.set_default_tensor_type('torch.DoubleTensor')


class Model:
    max_plate_nesting = 1

    def __init__(self, data):
        for key, value in data.items():
            key = key.lower()
            if isinstance(value, (list, np.ndarray)):
                value = torch.tensor(value, dtype=torch.double)
            self.__dict__[key] = value

    def __call__(self):
        """
        Notes
        -----
        Labeling system:
        1. for kernel level of parameters such as rho, span, nkots, kerenel etc.,
        use suffix _lev and _coef for levels and regression to partition
        2. for knots level of parameters such as coef, loc and scale priors,
        use prefix _lev and _rr _pr for levels, regular and positive regressors to partition
        3. reduce ambigious by replacing all greeks by labels more intuitive
        use _coef, _weight etc. instead of _beta, use _scale instead of _sigma
        """
        response = self.response
        n_obs = self.n_obs
        sdy = self.sdy
        dof = self.dof

        pr = self.pr
        rr = self.rr
        n_pr = self.n_pr
        n_rr = self.n_rr

        k_lev = self.k_lev
        k_coef = self.k_coef
        n_knots_lev = self.n_knots_lev
        n_knots_coef = self.n_knots_coef
        regressors = torch.zeros(n_obs)
        if n_pr > 0 and n_rr > 0:
            regressors = torch.cat([rr, pr], dim=-1)
        elif n_pr > 0:
            regressors = pr
        elif n_rr > 0:
            regressors = rr

        lev_knot_scale = self.lev_knot_scale

        # expand dim to n_rr x n_knots_coef
        rr_knot_pool_loc = self.rr_knot_pool_loc
        rr_knot_pool_scale = self.rr_knot_pool_scale
        rr_knot_scale = self.rr_knot_scale.unsqueeze(-1)

        # this does not need to expand dim since it is used as latent grand mean
        pr_knot_pool_loc = self.pr_knot_pool_loc
        pr_knot_pool_scale = self.pr_knot_pool_scale
        pr_knot_scale = self.pr_knot_scale.unsqueeze(-1)

        extra_out = {}

        # levels sampling
        lev_knot = pyro.sample("lev_knot", dist.Laplace(0, lev_knot_scale).expand([n_knots_lev]))
        lev = (lev_knot @ k_lev.transpose(-2, -1))

        # regular regressor sampling
        if n_rr > 0:
            # pooling latent variables
            rr_knot_loc = pyro.sample(
                "rr_knot_loc",
                dist.FoldedDistribution(
                    dist.Normal(rr_knot_pool_loc, rr_knot_pool_scale)
                )
            ).unsqueeze(-1) * torch.ones(n_rr, n_knots_coef)
            rr_knot = pyro.sample(
                "rr_knot",
                dist.FoldedDistribution(
                    dist.Normal(rr_knot_loc, rr_knot_scale)
                ).to_event(1)
            )
            rr_coef = (rr_knot @ k_coef.transpose(-2, -1)).transpose(-2, -1)

        # positive regressor sampling
        if n_pr > 0:
            # pooling latent variables
            pr_knot_loc = pyro.sample(
                "pr_knot_loc",
                dist.FoldedDistribution(
                    dist.Normal(pr_knot_pool_loc, pr_knot_pool_scale)
                )
            ).unsqueeze(-1) * torch.ones(n_pr, n_knots_coef)
            pr_knot = pyro.sample(
                "pr_knot",
                dist.FoldedDistribution(
                    dist.Normal(pr_knot_loc, pr_knot_scale)
                ).to_event(1)
            )
            pr_coef = (pr_knot @ k_coef.transpose(-2, -1)).transpose(-2, -1)

        # concatenating all latent variables
        coef_knot = torch.zeros(n_knots_coef)
        coef = torch.zeros(n_obs)
        if n_pr > 0 and n_rr > 0:
            coef_knot = torch.cat([rr_knot, pr_knot], dim=-2)
            coef = torch.cat([rr_coef, pr_coef], dim=-1)
        elif n_pr > 0:
            coef_knot = pr_knot
            coef = pr_coef
        elif n_rr > 0:
            coef_knot = rr_knot
            coef = rr_coef
        yhat = lev + (regressors * coef).sum(-1)

        # inject customize priors for coef at time t
        n_prior = self.n_prior
        if n_prior > 0:
            prior_mean = self.prior_mean
            prior_sd = self.prior_sd
            prior_tp_idx = self.prior_tp_idx.int()
            prior_idx = self.prior_idx.int()

            for m, sd, tp, idx in zip(prior_mean, prior_sd, prior_tp_idx, prior_idx):
                pyro.sample("prior_{}_{}".format(tp, idx), dist.Normal(m, sd),
                            obs=coef[..., tp, idx])

        pyro.sample("init_lev", dist.Normal(response[0], sdy), obs=lev[..., 0])

        obs_scale = pyro.sample("obs_scale", dist.HalfCauchy(sdy))
        with pyro.plate("response_plate", n_obs):
            pyro.sample("response", dist.StudentT(dof, yhat[..., :], obs_scale), obs=response)

        extra_out.update({'yhat': yhat, 'lev': lev, 'coef': coef, 'coef_knot': coef_knot})
        return extra_out
