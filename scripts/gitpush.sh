#!/bin/bash
git push --set-upstream origin $1
git checkout main
git branch -d $1